"""Summarize measured FPS and retained detection confidence; not accuracy."""
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import numpy as np

root=Path(__file__).resolve().parents[1]
runtime=Path('C:/dev/hanmir-runtime')
traces=[json.loads(x) for x in (root/'backend/logs/camera-analysis.jsonl').read_text(encoding='utf-8').splitlines()]
results={}
for name in ('yolo10-baseline','yolo10-measurement','yolo10-fast-measurement'):
    rows=[json.loads(x) for x in (runtime/(name+'.jsonl')).read_text(encoding='utf-8').splitlines()]
    rows=[r for r in rows if 'camera' in r]
    # Exclude first ten seconds for reconnect/model loading.
    start=datetime.fromisoformat(rows[0]['at'])
    stable=[r for r in rows if (datetime.fromisoformat(r['at'])-start).total_seconds()>=10]
    a,b=stable[0],stable[-1]
    seconds=(datetime.fromisoformat(b['at'])-datetime.fromisoformat(a['at'])).total_seconds()
    selected=[r for r in traces if a['at']<=r['at']<=b['at']]
    cats=defaultdict(list)
    for r in selected:
        for d in r['analysis'].get('detections',[]):
            if d.get('positive',True):cats[d['category']].append(d['confidence'])
    report={'seconds':seconds,'start':a['at'],'end':b['at'],
            'received_fps':(b['camera']['received_frames']-a['camera']['received_frames'])/seconds,
            'analysis_fps':(b['camera']['analysis_completed']-a['camera']['analysis_completed'])/seconds,
            'voice_active_samples':sum(r['camera']['voice_requests_active']>0 for r in stable),
            'samples':len(stable),'logged_frames':len(selected),
            'confidence':{k:{'count':len(v),'min':min(v),'mean':float(np.mean(v)),'max':max(v)} for k,v in cats.items()}}
    if selected:
        report['inference_ms_p50_p95_max']=np.percentile([r['inference_ms'] for r in selected],[50,95,100]).tolist()
        report['crop_frames']=sum(bool(r['analysis'].get('ppe_crop_attempted')) for r in selected)
        report['ppe_true_frames']={k:sum(r['analysis'].get('ppe',{}).get(k) is True for r in selected) for k in ('helmet','vest','glove')}
    results[name]=report
(runtime/'yolo10-comparison.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
