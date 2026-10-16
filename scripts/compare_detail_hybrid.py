"""Offline paired evidence; do not run while measuring live performance."""
import os,sys,json,shutil,time
from pathlib import Path
import cv2,torch
cv2.setNumThreads(1);torch.set_num_threads(2)
os.environ['HANMIR_YOLO_CPU_THREADS']='2'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.services import yolo_service as y
from app.services.openvino_yolo import load_openvino_yolo
from app.services.detail_model import HybridDetailModel
from app.config import settings
fixture=Path(sys.argv[1]);output=Path(sys.argv[2]);stride=int(sys.argv[3]) if len(sys.argv)>3 else 4
modes=sys.argv[4].split(',') if len(sys.argv)>4 else ('cpu','hybrid','hybrid_body','hybrid_body_early')
assert not output.exists()
settings.yolo_ppe_detail_interval_seconds=0;settings.camera_display_gamma=1.35;settings.camera_sharpen_amount=.2
settings.yolo_head_tight_probe=True
cpu=y.get_yolo_model();hybrid=HybridDetailModel(cpu,load_openvino_yolo(settings.yolo_openvino_model_path,2,'GPU'))
gpu960=None
if any("gpu960" in mode for mode in modes):
 gpu960=HybridDetailModel(cpu,hybrid.gpu,load_openvino_yolo("C:/dev/hanmir-runtime/gpu960/best_openvino_model",2,"GPU"))
rows=[]
for mode in modes:
 y._model=cpu if mode=='cpu' else gpu960 if 'gpu960' in mode else hybrid
 settings.yolo_vest_body_probe=mode.startswith('hybrid_body')
 settings.yolo_detail_early_exit=mode.endswith('_early')
 settings.yolo_vest_confidence = .25 if 'vest025' in mode else .30 if 'vest030' in mode else .35 if 'vest035' in mode else .40
 for f in sorted(fixture.glob('raw-*.jpg'))[::stride][:int(sys.argv[5]) if len(sys.argv)>5 else None]:
  target=y.CAPTURE_DIR/'_fixture'/('hybrid_'+f.name);target.parent.mkdir(exist_ok=True)
  shutil.copyfile(f,target);y._vision_state.clear();y._ppe_crop_last_at.clear()
  started=time.perf_counter();r=y.analyze_frame('_fixture/'+target.name,True);r.pop('_annotated_jpeg',None)
  rows.append(dict(mode=mode,file=f.name,ms=(time.perf_counter()-started)*1000,analysis=r));target.unlink()
  output.write_text(json.dumps(rows,indent=2),encoding='utf-8')
 print(mode,flush=True)
for mode in modes:
 r=[x for x in rows if x['mode']==mode]
 print(mode,{k:sum(any(d.get('category')==k and d.get('positive',True) for d in x['analysis']['detections']) for x in r) for k in ('helmet','vest','glove')},'samples',len(r),'mean_ms_excluding_first',sum(x['ms'] for x in r[1:])/max(1,len(r)-1))
