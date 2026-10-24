"""Summarize a JSON list of captured stationary UWB observations (not accuracy)."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import median,pstdev


def position_stats(rows,key):
    points=[r[key] for r in rows if r.get(key) and
            all(isinstance(r[key].get(k),(int,float)) and math.isfinite(r[key][k]) for k in ('x','y'))]
    if not points:return {'count':0}
    x=[p['x'] for p in points];y=[p['y'] for p in points]
    cx,cy=median(x),median(y)
    radii=sorted(math.hypot(p['x']-cx,p['y']-cy) for p in points)
    steps=[math.hypot(a['x']-b['x'],a['y']-b['y']) for a,b in zip(points,points[1:])]
    return dict(count=len(points),std_x_m=pstdev(x),std_y_m=pstdev(y),
        span_x_m=max(x)-min(x),span_y_m=max(y)-min(y),radius_p95_m=radii[int((len(radii)-1)*.95)],
        max_step_m=max(steps,default=0),coordinate_changes=sum(v>.001 for v in steps),
        apparent_path_m=sum(steps))


def analyze(rows):
    rows=sorted(rows,key=lambda r:r['logged_at_unix'])
    return dict(rows=len(rows),seconds=rows[-1]['logged_at_unix']-rows[0]['logged_at_unix'] if rows else 0,
        statuses=dict(Counter(r.get('status') for r in rows)),
        motion_states=dict(Counter(r.get('motion_filter',{}).get('mode','not_evaluated') for r in rows)),
        candidate=position_stats(rows,'candidate_position'),final=position_stats(rows,'final_position'),
        notice='Spread while declared stationary, not error against a surveyed ground-truth location.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();result=analyze(json.loads(args.input.read_text(encoding='utf-8')))
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result))
