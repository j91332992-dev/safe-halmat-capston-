import sys,time,json
from pathlib import Path
import numpy as np,torch
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.services.openvino_yolo import load_openvino_yolo
from app.services.yolo_service import get_yolo_model
files=sorted(Path('C:/dev/hanmir-runtime/camera-split-fixture').glob('raw-*.jpg'))
device=sys.argv[1] if len(sys.argv)>1 else 'CPU'
models={'pt':get_yolo_model(),'openvino':load_openvino_yolo(root/'backend/best_openvino_model',3,device)}
results={}
for name,model in models.items():
    torch.set_num_threads(3)
    model(str(files[0]),imgsz=640,conf=.25,verbose=False)
    rows=[]
    for f in files:
        start=time.perf_counter();r=model(str(f),imgsz=640,conf=.25,verbose=False)[0]
        rows.append(dict(file=f.name,ms=(time.perf_counter()-start)*1000,boxes=r.boxes.data.tolist()))
    results[name]=rows
checks=[]
for a,b in zip(results['pt'],results['openvino']):
    x=np.asarray(a['boxes']);y=np.asarray(b['boxes'])
    checks.append(dict(file=a['file'],same_shape=x.shape==y.shape,
        max_abs=float(np.max(np.abs(x-y))) if x.shape==y.shape and x.size else None))
results['checks']=checks
Path(f'C:/dev/hanmir-runtime/openvino-{device.lower()}-camera-comparison.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print({k:round(float(np.median([r['ms'] for r in v])),2) for k,v in results.items() if k!='checks'})
print(checks)
