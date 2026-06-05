from boxmot import Boxmot

boxmot = Boxmot(detector="yolov8n", tracker="bytetrack")
run = boxmot.track(source="videos/personas_lima1.mp4", show=True)
print(run)

#metrics = boxmot.val(benchmark="mot17-mini")
#print(metrics)
# 
#  boxmot track --detector yolov8n --reid osnet_x0_25_msmt17 --tracker deepocsort --source videos/personas_lima1.mp4 --show
# avg detector 50ms, avg tracker 1072 ms
# 
# boxmot track --detector yolov8n --tracker bytetrack --source videos/personas_lima1.mp4 --show
# avg detect 45, avg track 2.53
# ignores reid, only movement tracking