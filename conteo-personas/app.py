# Programa para contar visitantes
# Assigns id to object and tracks it until the object disappears
# Cuenta personas a menos de 3.2metros, que se queden 25 segundos o más en el stand 
# Todo: lee ultima cuenta desde un archivo
# 
from datetime import datetime
import time

import cv2
from boxmot.trackers import ByteTrack
from boxmot.trackers import OcSort
from ultralytics import YOLO
import numpy as np

def find_camera():
    max_indices = 20
    for i in range(max_indices):
        if i < -2:
            continue

        _cap = cv2.VideoCapture(i)
        if _cap.isOpened():
            _ret, _frame = _cap.read()
            if _ret:
                return _cap
            _cap.release()

    raise BlockingIOError(f"No se encontró cámara en rango {max_indices}")

def get_id_color(id: int):
    green = (128 + 25 % id) % 256
    blue = 25 * id % 256
    red = 50* id % 256
    return (blue, green, red)

def is_in_limits(box: tuple[int, int, int, int], w: int, h: int, w_limits=(0.1, 0.9), h_limits=(0.1, 0.8), max_dis=3.2):
    x1, y1, x2, y2 = box
    xc = (x1+x2)//2
    yc = (y1+y2)//2
    if xc < w_limits[0]*w or xc > w_limits[1]*w or yc < (1 - h_limits[1])*h or yc > (1-h_limits[0])*h:
        return False

    if y2 - y1 < (1.2/max_dis)*h:
        return False

    return True

class VisitorIds:
    def __init__(self) -> None:
        self.id_map_epoch: dict[int, float] = {}
        self.last_epoch_sync: float = 0

    def remove_lost_ids(self, _tracker: OcSort, time_sync=120):
        current_epoch = time.time()
        if current_epoch < self.last_epoch_sync + time_sync:
            return
        self.last_epoch_sync = current_epoch

        for id in self.id_map_epoch.copy():
            if current_epoch > self.id_map_epoch[id] + time_sync:
                _ = self.id_map_epoch.pop(id)
                
    def register_id(self, id: int, current_epoch: float):
        current_epoch = time.time()
        if id not in self.id_map_epoch:
            self.id_map_epoch[id] = current_epoch

    def is_visitor(self, id: int, current_epoch: float, visit_seconds=25.0) -> bool:
        if id in self.id_map_epoch:
            if current_epoch > self.id_map_epoch.get(id, 0) + visit_seconds:
                return True
        return False

class VisitorSet:
    def __init__(self):
        self.visitors = set()
        self.count_file = self.load_count()

    def add(self, id):
        if id not in self.visitors:
            self.save_count(self.get_count()+1)
            self.visitors.add(id)

    def get_count(self):
        return len(self.visitors) + self.count_file

    def save_count(self, count: int, path = "/tmp/visitor_count.txt"):
        print(count)
        with open(path, "w") as f:
            f.write(str(count))
    
    def load_count(self, path: str="/tmp/visitor_count.txt", default=0) -> int:
        try:
            with open(path) as f:
                return int(f.read())
        except (FileNotFoundError, ValueError):
            return default

        
if __name__ == "__main__":
    try:
        cap = find_camera()
        #cap = cv2.VideoCapture("videos/personas_lima1.mp4")
    except Exception as e:
        print(e)
        exit(1)

    tracker = OcSort()
    visitor_set = VisitorSet()
    visitor_ids = VisitorIds()

    model = YOLO("yolo26n.pt")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        h, w, _ = frame.shape

        results = model.predict(frame, classes=[0])
        detected_objects = []
        for r in results:
            boxes = r.boxes
            if boxes is None:
                continue
            for d in boxes.data:
                x1, y1, x2, y2, conf, cls, *rest = d
                if not is_in_limits((int(x1), int(y1), int(x2), int(y2)), w, h):
                    continue
                detected_objects.append([x1,y1,x2,y2,conf,cls])

        # dets: (N, 6) array with [x1, y1, x2, y2, conf, cls] per detection
        dets = np.array(detected_objects, dtype=np.float32)
        tracks = tracker.update(dets, frame)
        
        current_epoch = time.time()
        visitor_ids.remove_lost_ids(tracker)

        # tracks: (M, 8) array with [x1, y1, x2, y2, id, conf, cls, det_ind] per track
        for x1, y1, x2, y2, id, _conf, _cls, _ in tracks:
            x1, y1, x2, y2, id = int(x1), int(y1), int(x2), int(y2), int(id)
            color = get_id_color(id)
            cv2.rectangle(frame, (x1, y1), (x2, y2),color, 1)
            cv2.putText(frame, f"id: {id}", org=(x1, y1), fontFace=cv2.FONT_HERSHEY_DUPLEX, fontScale=0.6, color=color)

            visitor_ids.register_id(id, current_epoch=current_epoch)
            if visitor_ids.is_visitor(id, current_epoch):
                visitor_set.add(id)
            
        now = datetime.now()
        cv2.putText(frame, f"{now.strftime('%H:%M')} - stand Labotec", org=(20, 30), fontFace=cv2.FONT_HERSHEY_DUPLEX, fontScale=0.7, color=(50, 150, 20))
        cv2.putText(frame, f"Visitantes totales: {visitor_set.get_count()}", org=(20, 60), fontFace=cv2.FONT_HERSHEY_DUPLEX, fontScale=0.7, color=(50, 150, 20))
        
        cv2.imshow("Contador personas", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

