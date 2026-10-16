"""Development-only ROI sweep; never interpret tuning samples as held-out accuracy."""
import os,sys,json,time
from pathlib import Path
import cv2
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
os.environ['HANMIR_YOLO_CPU_THREADS']='2'
from app.services.yolo_service import get_yolo_model
model=get_yolo_model();rows=[]
for label,folder in [('worn','camera-split-fixture'),('bare','camera-barehead-fixture')]:
    for file in sorted((Path('C:/dev/hanmir-runtime')/folder).glob('raw-*.jpg')):
        image=cv2.imread(str(file));full=model(image,imgsz=640,conf=.25,verbose=False)[0]
        heads=[b.xyxy[0].tolist() for b in full.boxes if full.names[int(b.cls[0])]=='head' and float(b.conf[0])>=.5]
        if not heads:continue
        x1,y1,x2,y2=min(heads,key=lambda b:b[1]);w=x2-x1;h=y2-y1
        for pad in (.1,.3,.6):
            roi=image[max(0,int(y1-h*pad)):min(image.shape[0],int(y2+h*pad)),max(0,int(x1-w*pad)):min(image.shape[1],int(x2+w*pad))]
            lab=cv2.cvtColor(roi,cv2.COLOR_BGR2LAB);lab[:,:,0]=cv2.createCLAHE(clipLimit=2.,tileGridSize=(8,8)).apply(lab[:,:,0])
            for kind,view in [('original',roi),('clahe',cv2.cvtColor(lab,cv2.COLOR_LAB2BGR))]:
                for size in (320,480,640,960):
                    started=time.perf_counter();r=model(view,imgsz=size,conf=.25,verbose=False)[0]
                    helmet=[float(b.conf[0]) for b in r.boxes if r.names[int(b.cls[0])]=='helmet']
                    rows.append(dict(label=label,file=file.name,pad=pad,view=kind,size=size,helmet=max(helmet,default=0),ms=(time.perf_counter()-started)*1000))
        print(label,file.name,flush=True)
out=Path('C:/dev/hanmir-runtime/helmet-roi-sweep.json');out.write_text(json.dumps(rows,indent=2),encoding='utf-8')
summary=[]
for pad in (.1,.3,.6):
    for kind in ('original','clahe'):
        for size in (320,480,640,960):
            r=[x for x in rows if (x['pad'],x['view'],x['size'])==(pad,kind,size)]
            summary.append(dict(pad=pad,view=kind,size=size,worn=sum(x['helmet']>=.45 for x in r if x['label']=='worn'),bare=sum(x['helmet']>=.45 for x in r if x['label']=='bare')))
print(json.dumps(sorted(summary,key=lambda r:(r['bare'],-r['worn'])),indent=2))
