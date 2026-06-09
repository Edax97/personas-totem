# Body Parts Tracker using Ultralytics Pose Estimation
# Tracks keypoints (nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles)
# per detected person in real time, with the same frame-resizing logic as the visitor counter.
#

import argparse
from datetime import datetime
import time

import cv2
from ultralytics import YOLO
import numpy as np

# --------------------------------------------------------------------------- #
# COCO 17-keypoint skeleton: pairs of keypoint indices to draw limb lines
# NOTE: (0,5) and (0,6) — nose→shoulders — have been removed to avoid the
#       triangle that appeared over the face.
# --------------------------------------------------------------------------- #
SKELETON = [
    (0, 1), (0, 2),           # nose → eyes
    (1, 3), (2, 4),           # eyes → ears
    # (0, 5), (0, 6),         # ← removed: nose → shoulders caused face triangle
    (5, 6),                   # shoulders
    (5, 7), (7, 9),           # left arm
    (6, 8), (8, 10),          # right arm
    (5, 11), (6, 12),         # torso sides
    (11, 12),                 # hips
    (11, 13), (13, 15),       # left leg
    (12, 14), (14, 16),       # right leg
]

KEYPOINT_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder",
    "left_elbow", "right_elbow",
    "left_wrist", "right_wrist",
    "left_hip", "right_hip",
    "left_knee", "right_knee",
    "left_ankle", "right_ankle",
]

# Colour palette: one colour per keypoint index (BGR)
# Head keypoints → dark grey; upper body → mid grey; lower body → light grey
KP_COLORS = [
    (40,  40,  40),   # nose            – near black
    (50,  50,  50),   # left_eye        – dark grey
    (50,  50,  50),   # right_eye       – dark grey
    (60,  60,  60),   # left_ear        – dark grey
    (60,  60,  60),   # right_ear       – dark grey
    (100, 100, 100),  # left_shoulder   – mid grey
    (100, 100, 100),  # right_shoulder  – mid grey
    (120, 120, 120),  # left_elbow      – mid grey
    (120, 120, 120),  # right_elbow     – mid grey
    (140, 140, 140),  # left_wrist      – light-mid grey
    (140, 140, 140),  # right_wrist     – light-mid grey
    (160, 160, 160),  # left_hip        – light grey
    (160, 160, 160),  # right_hip       – light grey
    (180, 180, 180),  # left_knee       – lighter grey
    (180, 180, 180),  # right_knee      – lighter grey
    (200, 200, 200),  # left_ankle      – near white grey
    (200, 200, 200),  # right_ankle     – near white grey
]


# --------------------------------------------------------------------------- #
# Camera discovery (unchanged from original)
# --------------------------------------------------------------------------- #
def find_camera():
    max_indices = 20
    for i in range(max_indices):
        _cap = cv2.VideoCapture(i)
        if _cap.isOpened():
            _ret, _frame = _cap.read()
            if _ret:
                return _cap
            _cap.release()
    raise BlockingIOError(f"No se encontró cámara en rango {max_indices}")


# --------------------------------------------------------------------------- #
# Per-person colour (so each detected person gets a stable hue)
# --------------------------------------------------------------------------- #
def get_person_color(idx: int):
    """Return a dark-grey BGR colour (consistent with the black/grey palette)."""
    return (80, 80, 80)


# --------------------------------------------------------------------------- #
# Drawing helpers
# --------------------------------------------------------------------------- #
CONF_THRESHOLD = 0.4   # minimum keypoint confidence to draw


def draw_pose(frame, keypoints, person_color):
    """
    Draw skeleton limbs and keypoint dots for one person.

    keypoints : np.ndarray  shape (17, 3)  columns: x, y, conf
    """
    # Draw limb lines first so dots sit on top
    for a, b in SKELETON:
        xa, ya, ca = keypoints[a]
        xb, yb, cb = keypoints[b]
        if ca < CONF_THRESHOLD or cb < CONF_THRESHOLD:
            continue
        cv2.line(frame,
                 (int(xa), int(ya)),
                 (int(xb), int(yb)),
                 person_color, 2, cv2.LINE_AA)

    # Draw keypoint circles
    for idx, (x, y, conf) in enumerate(keypoints):
        if conf < CONF_THRESHOLD:
            continue
        dot_color = KP_COLORS[idx]
        cv2.circle(frame, (int(x), int(y)), 5, dot_color, -1, cv2.LINE_AA)
        cv2.circle(frame, (int(x), int(y)), 5, (255, 255, 255), 1, cv2.LINE_AA)


def draw_bounding_box(frame, box, color):
    """Draw bounding box without any text label."""
    x1, y1, x2, y2 = int(box[0]), int(box[1]), int(box[2]), int(box[3])
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 1)


def bb_area(box):
    """Return pixel area of a bounding box (xyxy format)."""
    return (box[2] - box[0]) * (box[3] - box[1])


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Body-parts tracker with Ultralytics pose")
    parser.add_argument("--width",  type=int, default=0,
                        help="Target display width  (0 = no resize)")
    parser.add_argument("--height", type=int, default=0,
                        help="Target display height (0 = no resize)")
    parser.add_argument("--video",  type=str, default="",
                        help="Path to a video file (default: webcam)")
    parser.add_argument("--model",  type=str, default="yolo11n-pose.pt",
                        help="Ultralytics pose model weights")
    parser.add_argument("--conf",   type=float, default=0.35,
                        help="Detection confidence threshold")
    args, _ = parser.parse_known_args()

    # Preserve scaling ratio (same logic as original)
    scale = 0.0
    if args.width > 0 and args.height > 0:
        scale = float(args.height) / float(args.width)

    # ------------------------------------------------------------------ #
    # Open capture source
    # ------------------------------------------------------------------ #
    if args.video:
        cap = cv2.VideoCapture(args.video)
        if not cap.isOpened():
            print(f"No se pudo abrir el archivo: {args.video}")
            exit(1)
    else:
        try:
            cap = find_camera()
        except BlockingIOError as e:
            print(e)
            exit(1)

    # ------------------------------------------------------------------ #
    # Load pose model
    # ------------------------------------------------------------------ #
    model = YOLO(args.model)

    print(f"Modelo cargado: {args.model}")
    print("Presiona 'q' para salir, 'n' para ocultar/mostrar nombres de keypoints.")

    show_kp_names = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w, _ = frame.shape

        # ---------------------------------------------------------------- #
        # Pose inference (track=True uses built-in ByteTrack so IDs persist)
        # ---------------------------------------------------------------- #
        results = model.track(frame,
                              persist=True,
                              conf=args.conf,
                              classes=[0],   # person only
                              verbose=False)

        # ---------------------------------------------------------------- #
        # Collect all detections, then keep only the nearest person
        # (nearest ≈ largest bounding-box area)
        # ---------------------------------------------------------------- #
        detections = []   # list of (area, kp_np, box_or_None, person_color)

        for r in results:
            if r.keypoints is None:
                continue

            boxes     = r.boxes
            keypoints = r.keypoints

            for i, kp in enumerate(keypoints.data):
                kp_np = kp.cpu().numpy()

                person_idx = i
                if boxes is not None and boxes.id is not None:
                    ids = boxes.id.cpu().numpy()
                    if i < len(ids):
                        person_idx = int(ids[i])

                person_color = get_person_color(person_idx)

                box = None
                area = 0.0
                if boxes is not None and i < len(boxes.xyxy):
                    box  = boxes.xyxy[i].cpu().numpy()
                    area = float(bb_area(box))

                detections.append((area, kp_np, box, person_color))

        # Pick the detection with the largest area (nearest person)
        if detections:
            detections.sort(key=lambda d: d[0], reverse=True)
            _, kp_np, box, person_color = detections[0]

            # Bounding box — no label
            if box is not None:
                draw_bounding_box(frame, box, person_color)

            # Skeleton & keypoints
            draw_pose(frame, kp_np, person_color)

            # Optional keypoint name labels
            if show_kp_names:
                for ki, (x, y, conf) in enumerate(kp_np):
                    if conf < CONF_THRESHOLD:
                        continue
                    cv2.putText(frame,
                                KEYPOINT_NAMES[ki],
                                (int(x) + 6, int(y) - 4),
                                cv2.FONT_HERSHEY_PLAIN, 0.75,
                                KP_COLORS[ki], 1, cv2.LINE_AA)

        # ---------------------------------------------------------------- #
        # HUD overlay — timestamp only (no person count, no person ID)
        # ---------------------------------------------------------------- #
        now = datetime.now()
        cv2.putText(frame,
                    f"{now.strftime('%H:%M')} | Estimacion de pose humana",
                    (20, 30),
                    cv2.FONT_HERSHEY_DUPLEX, 0.7, (50, 150, 20), 1, cv2.LINE_AA)

        # ---------------------------------------------------------------- #
        # Frame resize — identical logic to the original visitor counter
        # ---------------------------------------------------------------- #
        if args.width > 0 and args.height > 0:
            scale_frame   = float(h) / float(w)
            resize_width  = args.width
            resize_height = args.height
            if scale > scale_frame:
                resize_height = int(h * resize_width / w)
            else:
                resize_width  = int(w * resize_height / h)

            frame = cv2.resize(frame, (resize_width, resize_height))

        cv2.imshow("Pose tracker", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('n'):
            show_kp_names = not show_kp_names
            print("Nombres de keypoints:", "visibles" if show_kp_names else "ocultos")

    cap.release()
    cv2.destroyAllWindows()