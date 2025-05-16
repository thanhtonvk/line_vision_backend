import cv2
import numpy as np


def warp_point(pt, H):
    pt_h = np.array([[pt]], dtype="float32")
    pt_warped = cv2.perspectiveTransform(pt_h, H)
    return tuple(pt_warped[0][0])


def check_in_out(pt, w=300, h=600):
    x, y = pt
    return "IN" if 0 <= x <= w and 0 <= y <= h else "OUT"


def is_landing(track, i, threshold=15):
    if i < 1 or i + 1 >= len(track):
        return False
    d1 = np.linalg.norm(np.array(track[i]) - np.array(track[i - 1]))
    d2 = np.linalg.norm(np.array(track[i + 1]) - np.array(track[i]))
    return d1 > threshold and d2 < threshold
def to_background_coords(x, y, field_size=(300, 600), background_size=(500, 800)):
    field_width, field_height = field_size
    bg_width, bg_height = background_size

    scale_x = bg_width / field_width
    scale_y = bg_height / field_height

    bg_x = int(x * scale_x)
    bg_y = int(y * scale_y)

    bg_x = max(0, min(bg_x, bg_width))
    bg_y = max(0, min(bg_y, bg_height))

    return bg_x, bg_y
