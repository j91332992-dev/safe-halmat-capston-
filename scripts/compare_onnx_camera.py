import sys,time,json
from pathlib import Path
import numpy as np,torch
torch.set_num_threads(3)
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from ultralytics import YOLO
from app.services.onnx_yolo import load_onnx_yolo
files=sorted(Path('C:/dev/hanmir-runtime/camera-split-fixture').glob('raw-*.jpg'))
models={'pt':YOLO(str(root/'backend/best.pt')),'onnx':load_onnx_yolo(root/'backend/best.onnx',3)}
results={}
for name,model in models.items():
    model(str(files[0]),imgsz=640,conf=.25,verbose=False)
    rows=[]
    for f in files:
        start=time.perf_counter();r=model(str(f),imgsz=640,conf=.25,verbose=False)[0]
        rows.append(dict(file=f.name,ms=(time.perf_counter()-start)*1000,boxes=r.boxes.data.tolist()))
    results[name]=rows
checks=[]
for a,b in zip(results['pt'],results['onnx']):
    x=np.asarray(a['boxes']);y=np.asarray(b['boxes'])
    checks.append(dict(file=a['file'],same_shape=x.shape==y.shape,
        max_abs=float(np.max(np.abs(x-y))) if x.shape==y.shape and x.size else None))
results['checks']=checks
Path('C:/dev/hanmir-runtime/onnx-camera-comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print({k:round(float(np.median([r['ms'] for r in v])),2) for k,v in results.items() if k!='checks'})
print(checks)
