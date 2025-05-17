from flask import Flask, Response, request
from flask_socketio import SocketIO
import cv2
import time
import numpy as np
from collections import defaultdict
from ultralytics import YOLO
import os
import time
import eventlet

eventlet.monkey_patch()  # Patch các thư viện chuẩn để hoạt động với eventlet
from utils import check_in_out, is_landing, to_background_coords, warp_point
from flask import send_from_directory
import os

output_video_dir = "output_videos"
output_image_dir = "out_images"
output_time_file = "time_log.txt"
video_path = (
    "videos/Pickleball Thủ Đô TV Live Stream - Pickleball Thủ Đô TV (720p, h264).mp4"
)
out_video_path = os.path.join(output_video_dir, "full_video_output.mp4")
os.makedirs(output_video_dir, exist_ok=True)
os.makedirs(output_image_dir, exist_ok=True)
app = Flask(__name__)
# Cấu hình SocketIO với async_mode=eventlet để xử lý nhiều kết nối
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")
start_tracking = False

# Tạo mutex để đồng bộ hóa truy cập
video_lock = eventlet.semaphore.Semaphore()
# Mở video một lần và đóng khi ứng dụng tắt
cap = cv2.VideoCapture(video_path)

model = YOLO("models/best_ball.pt")
track_history = defaultdict(lambda: [])

# Khởi tạo thông số video
fps = cap.get(cv2.CAP_PROP_FPS)
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# VideoWriter sẽ được khởi tạo khi cần thiết
out = None

src_pts = None
dst_pts = np.float32([[0, 0], [300, 0], [300, 600], [0, 600]])
H = None
show_tracking = False

san_x = 300
san_y = 600


# Vẽ hình sân bóng từ 4 điểm góc trên frame
def draw_field(frame, src_pts):
    pts = src_pts.astype(np.int32).reshape((-1, 1, 2))  # Chuyển sang định dạng phù hợp
    cv2.polylines(frame, [pts], isClosed=True, color=(0, 255, 0), thickness=2)


@app.route("/output_videos/<filename>")
def download_video(filename):
    return send_from_directory("output_videos", filename)


@app.route("/out_images/<filename>")
def download_image(filename):
    return send_from_directory("out_images", filename)


@socketio.on("corner_points")
def handle_corners(data):
    global src_pts
    global H

    corner_points = data["points"]  # [{x:..., y:...}, ...]
    print("✅ Received corner points:", corner_points)

    # Chuyển thành NumPy array kiểu float32 với shape (4, 2)
    src_pts = np.array([[p["x"], p["y"]] for p in corner_points], dtype=np.float32)

    # Kiểm tra số lượng điểm
    if src_pts.shape != (4, 2):
        print("❌ Lỗi: cần đúng 4 điểm có dạng (x, y)")
        return

    # Tính ma trận biến đổi
    H = cv2.getPerspectiveTransform(src_pts, dst_pts)
    print("✅ Ma trận biến đổi H:", H)


@socketio.on("start_tracking")
def handle_start():
    global start_tracking, out
    start_tracking = True

    # Khởi tạo VideoWriter chỉ khi bắt đầu tracking
    if out is None:
        with video_lock:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # Sử dụng codec đơn giản hơn
            out = cv2.VideoWriter(
                out_video_path, fourcc, fps, (frame_width, frame_height)
            )

    print("Start tracking!")


@socketio.on("get_size")
def get_size():
    try:
        # Sử dụng video_lock để tránh xung đột
        with video_lock:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(width, height)
        socketio.emit("video_size", {"width": width, "height": height})
    except Exception as e:
        print(f"Lỗi khi lấy kích thước video: {e}")


@socketio.on("connect")
def handle_connect():
    print(f"Client connected: {request.sid}")


@socketio.on("disconnect")
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")


@socketio.on("stop_tracking")
def handle_stop():
    global start_tracking, out
    start_tracking = False
    with video_lock:
        if out is not None:
            out.release()
            print("Stopped video recording.")
            out = None  # Đặt lại để khi bắt đầu lại sẽ tạo mới

    socketio.emit(
        "stop_tracking",
        {
            "video": "output_videos/full_video_output.mp4",
            "time_log": "time_log.txt",
        },
    )


@socketio.on("show_tracking")
def handle_show_tracking():
    global show_tracking
    show_tracking = True


last_positions = []

from datetime import datetime


def generate_frames():
    global start_tracking, dst_pts, out, show_tracking
    with open(output_time_file, "w") as time_file:
        while True:
            with video_lock:  # Khóa để tránh xung đột truy cập
                success, frame = cap.read()

            if not success:
                break

            # Tạo bản sao để tránh xung đột
            current_frame = frame.copy()

            # Ghi frame vào video đầu ra nếu đang tracking
            if start_tracking and out is not None:
                try:
                    with video_lock:
                        out.write(frame)
                except Exception as e:
                    print(f"Lỗi khi ghi video: {e}")

            # Trong vòng lặp xử lý ảnh hoặc trong hàm xử lý khung hình:
            if src_pts is not None:
                draw_field(current_frame, src_pts)

            # Nếu có điểm và đang tracking
            if start_tracking and len(dst_pts) == 4:
                try:
                    result = model.track(
                        current_frame, persist=True, verbose=False, conf=0.3
                    )[0]
                    if result.boxes and result.boxes.id is not None:
                        boxes = result.boxes.xywh.cpu()
                        track_ids = [1 for _ in boxes]

                        for box, track_id in zip(boxes, track_ids):
                            x, y, w, h = box
                            track = track_history[track_id]
                            track.append((float(x), float(y)))
                            if len(track) > 30:
                                track.pop(0)
                            if show_tracking:
                                points = (
                                    np.hstack(track)
                                    .astype(np.int32)
                                    .reshape((-1, 1, 2))
                                )
                                cv2.polylines(
                                    current_frame,
                                    [points],
                                    isClosed=False,
                                    color=(230, 230, 230),
                                    thickness=2,
                                )
                        for track_id, track in track_history.items():
                            if len(track) >= 3:
                                for i in range(1, len(track) - 1):
                                    if is_landing(track, i):
                                        landing_pt = track[i]
                                        court_pt = warp_point(landing_pt, H)
                                        status = check_in_out(court_pt)
                                        cx, cy = map(int, court_pt)
                                        if (cx, cy) not in last_positions:
                                            # Cập nhật danh sách vị trí
                                            last_positions.append((cx, cy))
                                            if len(last_positions) > 30:
                                                last_positions.pop(
                                                    0
                                                )  # Giữ lại 30 vị trí gần nhất

                                            # Ghi file
                                            timestamp = time.strftime(
                                                "%H:%M:%S",
                                                time.gmtime(
                                                    cap.get(cv2.CAP_PROP_POS_MSEC)
                                                    / 1000
                                                ),
                                            )
                                            new_cx, new_cy = to_background_coords(cx,cy)
                                            time_file.write(
                                                f"{status};{timestamp};{new_cx};{new_cy}\n"
                                            )

                                            # Emit về client
                                            timestamp = time.strftime("%H:%M:%S")

                                            timestamp_name = datetime.now().strftime(
                                                "%Y%m%d_%H%M%S_%f"
                                            )
                                            filename = f"out_images/{status}_{timestamp_name}.png"
                                            cv2.imwrite(filename, frame)
                                            socketio.emit(
                                                "ball_status",
                                                {
                                                    "status": status,
                                                    "timestamp": timestamp,
                                                    "image": timestamp + ".png",
                                                    "x": new_cx,
                                                    "y": new_cy,
                                                },
                                            )
                except Exception as e:
                    print(f"Lỗi khi xử lý tracking: {e}")

            # Encode và gửi khung hình
            ret, buffer = cv2.imencode(".jpg", current_frame)
            frame_bytes = buffer.tobytes()
            yield (
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
            # Nhường luồng xử lý để các kết nối khác có thể hoạt động
            eventlet.sleep(0.03)


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


import socket  # thêm ở đầu file

if __name__ == "__main__":
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        finally:
            s.close()

        print(f"📡 Server is running at: http://{local_ip}:5000")
        print("🚀 Starting server on port 5000...")

        socketio.run(app, host="0.0.0.0", port=5000)
    finally:
        if out is not None:
            with video_lock:
                out.release()
        if cap.isOpened():
            with video_lock:
                cap.release()
