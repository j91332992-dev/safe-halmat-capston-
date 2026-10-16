import sys,json,shutil,time
from pathlib import Path
import torch
torch.set_num_threads(2)
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'backend'))
from app.services import yolo_service as y
from app.config import settings
results=[]
fixture=Path(sys.argv[1]) if len(sys.argv)>1 else Path('C:/dev/hanmir-runtime/camera-split-fixture')
settings.yolo_ppe_detail_interval_seconds=0
for enabled in (False,True):
    settings.yolo_head_detail_enabled=True; settings.yolo_head_tight_probe=True; settings.camera_display_gamma=1.35 if enabled else 1.2; settings.camera_sharpen_amount=.2 if enabled else 0.0
    for file in sorted(fixture.glob('raw-*.jpg')):
        dest=y.CAPTURE_DIR/'_fixture'/('fixture_'+file.name);dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(file,dest)
        y._vision_state.clear();y._ppe_crop_last_at.clear()
        started=time.perf_counter();r=y.analyze_frame('_fixture/'+dest.name,True);r.pop('_annotated_jpeg',None)
        results.append(dict(head_enabled=enabled,file=file.name,ms=(time.perf_counter()-started)*1000,analysis=r))
        dest.unlink()
path=Path('C:/dev/hanmir-runtime')/(fixture.name+'-bright135-comparison.json');path.write_text(json.dumps(results,indent=2),encoding='utf-8')
for enabled in (False,True):
    rows=[r for r in results if r['head_enabled']==enabled]
    print('head',enabled,{k:sum(any(d['category']==k and d.get('positive',True) for d in r['analysis']['detections']) for r in rows) for k in ('helmet','vest','glove')})



