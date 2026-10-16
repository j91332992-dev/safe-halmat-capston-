"""Offline hand ROI probe; logs real glove classes without relabeling hands."""
import sys,json,time,os
from pathlib import Path
import cv2
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
os.environ['HANMIR_YOLO_CPU_THREADS']='2';cv2.setNumThreads(1)
from app.services.yolo_service import get_yolo_model,_category
from app.services.camera_brightness import brighten
model=get_yolo_model();out=[]
fixture=Path('C:/dev/hanmir-runtime/camera-worn-validation2')
for file in sorted(fixture.glob('raw-*.jpg')):
    image=cv2.imread(str(file));full=model(image,imgsz=640,conf=.25,verbose=False)[0]
    corrected=brighten(image)
    hands=[b for b in full.boxes if full.names[int(b.cls[0])]=='hand' and float(b.conf[0])>=.4]
    for index,hand in enumerate(hands[:2]):
        x1,y1,x2,y2=hand.xyxy[0].tolist();w=x2-x1;h=y2-y1
        for pad in (.3,.7):
            x=max(0,int(x1-w*pad));y=max(0,int(y1-h*pad))
            roi=corrected[y:min(image.shape[0],int(y2+h*pad)),x:min(image.shape[1],int(x2+w*pad))]
            if not roi.size:continue
            started=time.perf_counter();r=model(roi,imgsz=480,conf=.25,verbose=False)[0]
            candidates=[dict(name=r.names[int(b.cls[0])],confidence=float(b.conf[0]),box=b.xyxy[0].tolist()) for b in r.boxes]
            gloves=[d for d in candidates if _category(d['name'])==('glove',True)]
            out.append(dict(file=file.name,hand=index,pad=pad,origin=[x,y],candidates=candidates,glove=max((d['confidence'] for d in gloves),default=0),ms=(time.perf_counter()-started)*1000))
Path('C:/dev/hanmir-runtime/glove-roi-probe.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
for pad in (.3,.7):print(pad,sorted({r['file'] for r in out if r['pad']==pad and r['glove']>=.4}))
