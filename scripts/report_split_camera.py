import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import numpy as np
root=Path(__file__).resolve().parents[1];runtime=Path('C:/dev/hanmir-runtime')
traces=[]
for p in (root/'backend/logs').glob('camera-analysis.jsonl*'):
    for line in p.read_text(encoding='utf-8').splitlines():
        try:traces.append(json.loads(line))
        except ValueError:pass
results={}
for name in ('yolo-split-measurement','yolo-split-tuned-measurement','yolo-split-final-measurement','yolo-split-callback-measurement','yolo-gpu-measurement','yolo-bright-measurement','yolo-bright-limited-measurement','yolo-bright135-measurement','yolo-paced-measurement'):
    rows=[json.loads(x) for x in (runtime/(name+'.jsonl')).read_text().splitlines()]
    rows=[r for r in rows if 'camera' in r];start=datetime.fromisoformat(rows[0]['at'])
    rows=[r for r in rows if (datetime.fromisoformat(r['at'])-start).total_seconds()>=15]
    a,b=rows[0],rows[-1];seconds=(datetime.fromisoformat(b['at'])-datetime.fromisoformat(a['at'])).total_seconds()
    result={'start':a['at'],'end':b['at'],'seconds':seconds,
            'received_fps':(b['camera']['received_frames']-a['camera']['received_frames'])/seconds,
            'fast_fps':(b['camera']['analysis_completed']-a['camera']['analysis_completed'])/seconds,
            'detail_fps':(b['camera']['detail_completed']-a['camera']['detail_completed'])/seconds,
            'voice_active_samples':sum(r['camera']['voice_requests_active']>0 for r in rows),'sample_count':len(rows)}
    selected=[r for r in traces if a['at']<=r['at']<=b['at']]
    for lane in ('fast','detail'):
        lane_rows=[r for r in selected if r.get('lane')==lane];classes=defaultdict(list)
        for r in lane_rows:
            for d in r['analysis'].get('detections',[]):
                if d.get('positive',True):classes[d['category']].append(d['confidence'])
        if lane_rows:
            result[lane]={'frames':len(lane_rows),'ms_p50_p95_max':np.percentile([r['inference_ms'] for r in lane_rows],[50,95,100]).tolist(),
                'classes':{k:{'count':len(v),'min':min(v),'mean':float(np.mean(v)),'max':max(v)} for k,v in classes.items()},
                'fresh_detail_frames':sum(bool(r['analysis'].get('detail_evidence',{}).get('valid')) for r in lane_rows)}
    results[name]=result
(runtime/'split-camera-summary.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
