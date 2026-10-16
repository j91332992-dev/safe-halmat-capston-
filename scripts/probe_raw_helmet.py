import json,time
from pathlib import Path
import cv2,torch
torch.set_num_threads(2)
from ultralytics import YOLO
root=Path(__file__).resolve().parents[1]
model=YOLO(str(root/'backend/best.pt'))
rows=[]
for file in sorted(Path('C:/dev/hanmir-runtime/camera-split-fixture').glob('raw-*.jpg')):
    image=cv2.imread(str(file))
    full=model(image,imgsz=640,conf=.25,verbose=False)[0]
    heads=[b.xyxy[0].tolist() for b in full.boxes if full.names[int(b.cls[0])]=='head' and float(b.conf[0])>.5]
    views=[('full640',image,640)]
    if heads:
        x1,y1,x2,y2=min(heads,key=lambda b:b[1]);w=x2-x1;h=y2-y1
        roi=image[max(0,int(y1-h*.3)):min(image.shape[0],int(y2+h*.4)),max(0,int(x1-w*.3)):min(image.shape[1],int(x2+w*.3))]
        views += [('head320',roi,320),('head640',roi,640),('head960',roi,960)]
    for name,view,size in views:
        started=time.perf_counter();r=model(view,imgsz=size,conf=.25,verbose=False)[0]
        rows.append(dict(file=file.name,view=name,ms=(time.perf_counter()-started)*1000,
            detections=[dict(name=r.names[int(b.cls[0])],confidence=float(b.conf[0])) for b in r.boxes]))
Path('C:/dev/hanmir-runtime/raw-helmet-probe.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
for r in rows:
    print(r['file'],r['view'],[(d['name'],round(d['confidence'],3)) for d in r['detections'] if d['name'] in ('helmet','head')])
