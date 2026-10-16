import json,time,math,collections
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
from types import SimpleNamespace
def least_squares(fun, initial, bounds):
 p=np.array(initial,float);lo=np.array(bounds[0]);hi=np.array(bounds[1]);damping=.001
 for _ in range(100):
  e=fun(p);j=np.column_stack([(fun(p+np.eye(3)[i]*1e-5)-e)/1e-5 for i in range(3)])
  step=np.linalg.solve(j.T@j+damping*np.eye(3),-j.T@e);q=np.clip(p+step,lo,hi)
  if np.sum(fun(q)**2)<np.sum(e**2):
   p=q;damping=max(1e-8,damping*.3)
   if np.linalg.norm(step)<1e-8:break
  else:damping*=10
 return SimpleNamespace(x=p,fun=fun(p))
import argparse
parser=argparse.ArgumentParser(description='Capture stationary UWB range and position metrics; room fits are assumption-based, not surveyed dimensions.')
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--start', help='ISO timestamp; default now')
parser.add_argument('--seconds', type=float, default=60)
parser.add_argument('--logs', type=Path, default=Path(__file__).resolve().parents[1]/'backend/logs')
args=parser.parse_args()
root=args.output;root.mkdir(parents=True,exist_ok=True)
start=datetime.fromisoformat(args.start).timestamp() if args.start else time.time();end=start+args.seconds
while time.time()<end:time.sleep(min(1,end-time.time()))
rows=[]
for p in args.logs.glob('uwb-observations.jsonl*'):
 if not p.is_file():continue
 for s in p.open(encoding='utf-8'):
  try:r=json.loads(s)
  except ValueError:continue
  if start<=r.get('logged_at_unix',0)<=end:rows.append(r)
rows.sort(key=lambda r:r['logged_at_unix'])
(root/'uwb-stationary.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in rows),encoding='utf-8')
def stats(v):
 a=np.array(v,float);return {'n':len(a),'median':float(np.median(a)),'min':float(a.min()),'max':float(a.max()),'std':float(a.std()),'p05_p95':np.percentile(a,[5,95]).tolist()} if len(a) else None
out={'start':datetime.fromtimestamp(start,timezone.utc).isoformat(),'seconds':args.seconds,'cycles':len(rows),'status':dict(collections.Counter(r.get('status') for r in rows)),'reason':dict(collections.Counter(r.get('reason') for r in rows if r.get('reason'))),'anchors':{}}
for aid in ('anchor-001','anchor-002','anchor-003','anchor-004'):
 obs=[o for r in rows for o in r['input']['observations'] if o['anchor_id']==aid];ms=[m for r in rows for m in r.get('processed_measurements',[]) if m['anchor_id']==aid]
 raw=[o['raw_distance_m'] for o in obs if o.get('raw_distance_m') is not None]
 out['anchors'][aid]={'status':dict(collections.Counter(o['status'] for o in obs)),'raw_m':stats(raw),'filtered_m':stats([m['distance_m'] for m in ms]),'raw_step_m':stats(np.abs(np.diff(raw))),'quality':dict(collections.Counter(m.get('signal_quality',{}).get('classification') for m in ms)),'diagnostics':{k:stats([o['diagnostics'][k] for o in obs if o.get('diagnostics',{}).get(k) is not None]) for k in ('rx_power_dbm','first_path_power_dbm','power_difference_db','peak_minus_first_path_samples')}}
for key in ('candidate_position','filtered_position','final_position'):
 pts=np.array([[r[key]['x'],r[key]['y']] for r in rows if r.get(key) and r[key].get('x') is not None]);c=np.median(pts,axis=0) if len(pts) else None
 if c is not None:
  out[key]={'n':len(pts),'center':c.tolist(),'span_xy':np.ptp(pts,axis=0).tolist(),'radius_from_median_m':stats(np.linalg.norm(pts-c,axis=1)),'step_m':stats(np.linalg.norm(np.diff(pts,axis=0),axis=1))}
out['confidence']=stats([r['confidence'] for r in rows if 'confidence' in r]);out['server_interval_seconds']=stats(np.diff([r['logged_at_unix'] for r in rows]));out['room_assumption_fits']=[]
d=np.array([out['anchors'][a]['raw_m']['median'] for a in out['anchors']])
for ratio in (5/3.3,1,2):
 for dz in (0,1):
  def errors(p):
   h,u,v=p;w=h*ratio;x=w*u;y=h*v
   return np.sqrt(np.array([x*x+y*y,(x-w)**2+y*y,(x-w)**2+(y-h)**2,x*x+(y-h)**2])+dz*dz)-d
  f=least_squares(errors,[3,.5,.5],bounds=([.5,0,0],[20,1,1]))
  h,u,v=f.x;out['room_assumption_fits'].append({'aspect_X_over_Y':ratio,'assumed_vertical_gap_m':dz,'X_m':h*ratio,'Y_m':h,'tag_xy_m':[h*ratio*u,h*v],'residual_rmse_m':float(np.sqrt(np.mean(f.fun**2)))})
(root/'uwb-stationary-summary.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
