"""Fixed-image diagnostic. Raw class/confidence evidence, no threshold changes."""
import json,time,sys
from pathlib import Path
import torch,cv2
torch.set_num_threads(3)
from ultralytics import YOLO
root=Path(__file__).resolve().parents[1]
model=YOLO(str(root/'backend/best.pt'))
image=cv2.imread('C:/dev/hanmir-runtime/yolo10-frame.jpg')
rows=[]
for name,img in [('full',image),('upper_half',image[:image.shape[0]//2]),('head_region',image[:int(image.shape[0]*.45),int(image.shape[1]*.15):int(image.shape[1]*.85)])]:
    for size in (320,640,960):
        start=time.perf_counter()
        r=model(img,imgsz=size,conf=.25,verbose=False)[0]
        rows.append(dict(view=name,size=size,ms=(time.perf_counter()-start)*1000,
                         detections=[dict(name=r.names[int(b.cls[0])],confidence=float(b.conf[0]),box=b.xyxy[0].tolist()) for b in r.boxes]))
out={'names':model.names,'rows':rows}
Path('C:/dev/hanmir-runtime/helmet-fixed-probe.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps(out,indent=2))
