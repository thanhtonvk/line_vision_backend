
# Pickleball Ball Tracking Server (Flask + Socket.IO)

Đây là hệ thống xử lý video và theo dõi quả bóng trong môn Pickleball sử dụng tracknet, Flask, và Socket.IO.

## 📡 API WebSocket

Dưới đây là danh sách các sự kiện (event) được hỗ trợ bởi Socket.IO:

---

### 1. `connect`

- **Mô tả**: Kích hoạt khi client kết nối đến server.
- **Phản hồi**: In ra `Client connected: [session id]`.

---

### 2. `disconnect`

- **Mô tả**: Kích hoạt khi client ngắt kết nối khỏi server.
- **Phản hồi**: In ra `Client disconnected: [session id]`.

---

### 3. `corner_points`

- **Gửi từ client**
- **Payload**: 
  ```json
  {
    "points": [
      {"x": ..., "y": ...},
      {"x": ..., "y": ...},
      {"x": ..., "y": ...},
      {"x": ..., "y": ...}
    ]
  }
  ```
- **Mô tả**: Cung cấp 4 điểm góc sân để tính toán ma trận biến đổi phối cảnh.
- **Phản hồi**: In ra ma trận biến đổi `H`.

---

### 4. `start_tracking`

- **Gửi từ client**
- **Mô tả**: Bắt đầu quá trình theo dõi bóng và ghi lại video đầu ra.
- **Phản hồi**: Ghi video vào `output_videos/full_video_output.mp4`.

---

### 5. `stop_tracking`

- **Gửi từ client**
- **Mô tả**: Dừng việc theo dõi bóng và đóng ghi video.
- **Phản hồi**: 
  ```json
  {
    "video": "output_videos/full_video_output.mp4",
    "time_log": "time_log.txt"
  }
  ```

---

### 6. `get_size`

- **Gửi từ client**
- **Mô tả**: Yêu cầu lấy kích thước video.
- **Phản hồi**:
  ```json
  {
    "width": ..., 
    "height": ...
  }
  ```

---

### 7. `show_tracking`

- **Gửi từ client**
- **Mô tả**: Yêu cầu hiển thị đường đi của bóng trên video.

---

### 8. `ball_status` (phát từ server)

- **Mô tả**: Server gửi mỗi khi phát hiện điểm rơi mới của bóng.
- **Payload**:
  ```json
  {
    "status": "in" | "out",
    "timestamp": "HH:MM:SS",
    "image": "timestamp.png",
    "x": int,
    "y": int
  }
  ```

---

## 📷 API HTTP

### 1. `GET /video_feed`

- **Mô tả**: Trả về video stream MJPEG từ quá trình xử lý.

### 2. `GET /output_videos/<filename>`

- **Mô tả**: Tải video đã được ghi.

### 3. `GET /out_images/<filename>`

- **Mô tả**: Tải hình ảnh snapshot được ghi lại khi bóng rơi.

---

## 📁 Output Files

- `output_videos/full_video_output.mp4`: Video đầu ra toàn bộ quá trình.
- `out_images/`: Hình ảnh điểm rơi được chụp kèm thời gian.
- `time_log.txt`: Ghi log thời gian, trạng thái (in/out), và tọa độ bóng.

---

## 🧠 Mô hình sử dụng

- `models/best_ball.pt`: Mô hình tracknet huấn luyện riêng để phát hiện bóng.
