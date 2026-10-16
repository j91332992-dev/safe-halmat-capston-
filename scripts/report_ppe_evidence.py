"""Report sampled UI states and unique fresh detail evidence separately."""
import json,sys,collections
from pathlib import Path
p=Path(sys.argv[1]);rows=[json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]
detail={x['analysis']['analysis']['detail_evidence']['frame_id']:x['analysis']['analysis']['detail_evidence'] for x in rows if x['analysis']['analysis'].get('detail_evidence',{}).get('valid')}
result={'samples':len(rows),'unique_fresh_detail_frames':len(detail),'categories':{},'truth':rows[0]['truth'],
 'limitations':'Small single-scene sample; confidence is not accuracy. Adjacent raw images are not atomic with analysis.'}
for key in ('helmet','vest','glove'):
 selected=[]
 for d in detail.values():
  candidates=[v for v in d['detections'] if v.get('category')==key and v.get('positive',True)]
  selected.append(max(candidates,key=lambda v:v['confidence']) if candidates else None)
 scores=[v['confidence'] for v in selected if v]
 result['categories'][key]={'detail_detected':len(scores),'confidence_min_max':[min(scores),max(scores)] if scores else None,
  'sources':dict(collections.Counter(v.get('source','full') for v in selected if v)),
  'color_assisted':sum('red_pixel_ratio' in v for v in selected if v),
  'ui_state_counts':dict(collections.Counter(str(x['analysis']['analysis'].get('ppe',{}).get(key)) for x in rows))}
p.with_name('summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
