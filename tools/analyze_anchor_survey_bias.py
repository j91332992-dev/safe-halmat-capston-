"""Read-only survey/reference comparison. Never writes calibration or layout."""
import argparse
import json
import math
from pathlib import Path
from statistics import median
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.database import SessionLocal
from app.models.entities import AnchorSurvey
from app.services.uwb_timestamp_audit import audit_timestamp


def analyze(row,width,height):
    samples=json.loads(row.samples_json)
    evaluated={p['pair']:p for p in json.loads(row.result_json).get('pairs',[])}
    expected={'1-2':width,'3-4':width,'1-4':height,'2-3':height,
              '1-3':math.hypot(width,height),'2-4':math.hypot(width,height)}
    anchors=sorted(json.loads(row.baseline_json)['design']['anchors'],key=lambda a:a['anchor_id'])
    result=[]
    for key in ('1-2','1-3','1-4','2-3','2-4','3-4'):
        a,b=map(int,key.split('-'))
        ss=[s for s in samples if s['a']==a and s['b']==b]
        dz=abs(anchors[a-1]['z']-anchors[b-1]['z'])
        reference=math.hypot(expected[key],dz)
        values=sorted(s['distance_m'] for s in ss)
        audit=[audit_timestamp(s) for s in ss]
        checked=[r for r in audit if r['status'] in ('match','mismatch')]
        middle=median(values) if values else None
        result.append(dict(pair=key,reference_spatial_m=reference,count=len(ss),
            raw_median_m=middle,raw_median_error_m=middle-reference if middle is not None else None,
            raw_p90_p10_m=values[int((len(values)-1)*.9)]-values[int((len(values)-1)*.1)] if values else None,
            invalid_diagnostic=sum(not s['diagnostic_valid'] for s in ss),
            severe_multipath=sum(s['gap_db']>=12 and abs(s['path_samples'])>=10 for s in ss),
            timestamp_audited=len(checked),timestamp_mismatches=sum(r['status']=='mismatch' for r in audit),
            clock_ppm_median=median(r['clock_ppm'] for r in checked) if checked else None,
            clock_correction_m_median=median(r['clock_correction_m'] for r in checked) if checked else None,
            ranging_methods=sorted(set(r['ranging_method'] for r in checked)),
            same_exchange_ss_median=median(r['ss_comparison_m'] for r in checked) if checked else None,
            recomputation_max_error_m=max(abs(r['reported_delta_m']) for r in checked) if checked else None,
            original_decision=evaluated.get(key)))
    return dict(session_id=row.session_id,status=row.status,
        reference_xy_m=[width,height],reference_assumption='Rectangular antenna centers; registered relative heights are correct.',
        calibration_applied=False,pairs=result)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width',type=float,required=True)
    parser.add_argument('--height',type=float,required=True)
    parser.add_argument('--session',action='append',default=[])
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if not all(math.isfinite(v) and v>0 for v in (args.width,args.height)):
        parser.error('reference dimensions must be finite and positive')
    with SessionLocal() as db:
        rows=[db.get(AnchorSurvey,s) for s in args.session] if args.session else [db.query(AnchorSurvey).order_by(AnchorSurvey.created_at.desc()).first()]
        if any(r is None for r in rows):parser.error('survey session not found')
        result=[analyze(r,args.width,args.height) for r in rows]
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    for report in result:
        print(report['session_id'],report['status'])
        for p in report['pairs']:
            print(json.dumps({k:p[k] for k in ('pair','count','raw_median_error_m','timestamp_audited','timestamp_mismatches','clock_correction_m_median')},ensure_ascii=False))


if __name__=='__main__':
    main()
