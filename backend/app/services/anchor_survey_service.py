"""Ten-second anchor survey proposals; never changes a live layout implicitly."""
import hashlib
import json
import math
from statistics import median

from ..database import utcnow
from ..models.entities import AnchorSurvey, EvacuationIncident, LayoutDraft
from .uwb_timestamp_audit import audit_timestamp

PAIRS = ((1,2),(1,3),(1,4),(2,3),(2,4),(3,4))
ACTIVE = ('requested', 'measuring')


def fingerprint(design):
    stable = json.loads(json.dumps(design))
    stable.pop('saved_at', None)
    stable.pop('survey_session_id', None)
    for a in stable.get('anchors', []):
        a.pop('online', None)
        a.pop('last_seen', None)
    return hashlib.sha256(json.dumps(stable, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def baseline(db, site_id):
    from ..routers.layout import applied_design
    current = applied_design(db, site_id)
    draft = db.get(LayoutDraft, site_id)
    design = json.loads(draft.draft_json) if draft else current
    return dict(current=fingerprint(current), draft=fingerprint(design), design=design)


def fire_active(db, site_id):
    return db.query(EvacuationIncident).filter(EvacuationIncident.site_id == site_id,
        EvacuationIncident.status.in_(('active', 'pending_manager'))).first() is not None


def expire(db, site_id):
    for row in db.query(AnchorSurvey).filter(AnchorSurvey.site_id == site_id, AnchorSurvey.status.in_(ACTIVE)):
        now = utcnow()
        deadline = row.started_at or row.created_at
        seconds = 25 if row.started_at else 30
        if fire_active(db, site_id) or (now-deadline).total_seconds() > seconds:
            row.status = 'cancelled' if fire_active(db, site_id) else 'timed_out'
            row.finished_at = now
            row.result_json = json.dumps(dict(reasons=['화재 대응 중 측량 취소' if row.status == 'cancelled' else '장치 측량 응답 시간 초과']))
    # Sessions use autoflush=False; command polling must see cancelled rows
    # removed from the active SQL query in this same request.
    db.flush()


def serialize(row):
    if not row:
        return None
    base = json.loads(row.baseline_json)
    elapsed = (utcnow()-row.started_at).total_seconds() if row.started_at else 0
    return dict(session_id=row.session_id, status=row.status, result=json.loads(row.result_json),
        created_at=row.created_at.isoformat()+'Z', elapsed_seconds=max(0, min(10, elapsed)),
        old_site=base['design']['site'], anchor_ids=[a['anchor_id'] for a in base['design']['anchors']])


def evaluate(samples, anchors):
    heights = {i+1: float(a['z']) for i,a in enumerate(anchors)}
    groups = {f'{a}-{b}': [] for a,b in PAIRS}
    seen = set()
    for s in samples:
        pair = tuple(sorted((s['a'],s['b'])))
        key = f'{pair[0]}-{pair[1]}'
        identity = (s['a'],s['b'],s['sequence'],s['elapsed_ms'])
        if key not in groups or identity in seen:
            continue
        seen.add(identity)
        dz = abs(heights[s['a']]-heights[s['b']])
        distance = s['distance_m']
        timestamp_audit = audit_timestamp(s)
        bad = not s['diagnostic_valid'] or (s['gap_db'] >= 12 and abs(s['path_samples']) >= 10) or timestamp_audit['status'] not in ('match','unavailable')
        horizontal = math.sqrt(distance*distance-dz*dz) if distance > dz else None
        groups[key].append(dict(**s, horizontal_m=horizontal, excluded=bad or horizontal is None,timestamp_audit=timestamp_audit))
    pairs = []
    reasons = []
    distances = {}
    for key, entries in groups.items():
        valid = [s for s in entries if not s['excluded']]
        values = [s['horizontal_m'] for s in valid]
        middle = median(values) if values else 0
        mad = median(abs(v-middle) for v in values) if values else 0
        selected = [s for s in valid if abs(s['horizontal_m']-middle) <= max(.15,3*1.4826*mad)]
        retained = sorted(s['horizontal_m'] for s in selected)
        span = (max(s['elapsed_ms'] for s in selected)-min(s['elapsed_ms'] for s in selected))/1000 if selected else 0
        count, total = len(retained),len(entries)
        # Huber location: bound each residual's influence, then also downweight
        # weak/multipath diagnostics. Do not select values to match the old map.
        average = median(retained) if retained else None
        sigma = max(.03,1.4826*median(abs(v-average) for v in retained)) if retained else .03
        if retained:
            for _ in range(8):
                weighted = []
                for sample in selected:
                    residual = abs(sample['horizontal_m']-average)
                    robust = min(1.0,1.5*sigma/max(residual,1e-9))
                    signal = .35 if sample['gap_db']>=6 or abs(sample['path_samples'])>=4 else 1.0
                    weighted.append((sample['horizontal_m'],robust*signal))
                updated = sum(v*w for v,w in weighted)/sum(w for _,w in weighted)
                if abs(updated-average)<.0001:
                    average=updated;break
                average=updated
        # Two substantial separated modes are ambiguous, not a license to pick
        # whichever cluster creates a convenient room size.
        split = False
        if len(values)>=8:
            ordered=sorted(values)
            for i in range(2,len(ordered)-3):
                if ordered[i+1]-ordered[i]>.25 and min(i+1,len(ordered)-i-1)/len(ordered)>=.3:
                    split=True;break
        spread = retained[min(count-1,int((count-1)*.9))]-retained[int((count-1)*.1)] if retained else None
        rejected = (total-count)/total if total else 1
        ok = count >= 8 and span >= 6 and rejected <= .3 and not split and spread is not None and spread <= max(.3,.08*average)
        if not ok:
            reasons.append(f'{key} 표본 부족 또는 변동/제외율 초과')
        if average is not None:
            distances[key] = average
        pairs.append(dict(pair=key, count=count, total=total,
            estimate_m=round(average,3) if average else None, estimator='huber_signal_weighted', multimodal=split,
            median_m=round(middle,3) if values else None, mad_m=round(mad,4),
            spread_m=round(spread,3) if spread is not None else None,
            span_seconds=round(span,2), rejected_ratio=round(rejected,3), passed=ok,
            timestamp_audited=sum(s['timestamp_audit']['status']=='match' for s in entries),
            timestamp_failed=sum(s['timestamp_audit']['status'] not in ('match','unavailable') for s in entries)))
    width = (distances['1-2']+distances['3-4'])/2 if '1-2' in distances and '3-4' in distances else None
    height = (distances['1-4']+distances['2-3'])/2 if '1-4' in distances and '2-3' in distances else None
    if width and height:
        for a,b,dimension in [('1-2','3-4',width),('1-4','2-3',height)]:
            if abs(distances[a]-distances[b]) > max(.3,dimension*.08):
                reasons.append(f'{a}와 {b} 맞은편 변 길이 불일치')
        diagonal = math.hypot(width,height)
        for key in ['1-3','2-4']:
            if key not in distances or abs(distances[key]-diagonal) > max(.3,diagonal*.08):
                reasons.append(f'{key} 대각선 불일치')
        if not (.5 <= width <= 100 and .5 <= height <= 100):
            reasons.append('제안 크기가 허용 범위를 벗어남')
    return dict(passed=not reasons, width=round(width,3) if width else None,
        height=round(height,3) if height else None, pairs=pairs, reasons=reasons,
        notice='앵커 사각형의 치수이며 실제 벽·출구·장애물을 자동 인식한 결과가 아닙니다.')


def object_issues(design):
    w,h = design['site']['width'],design['site']['height']
    issues = []
    for o in design.get('obstacles', []):
        x,y,ow,oh = o['x'],o['y'],o['width'],o['height']
        if min(x,y) < 0 or x+ow > w+.001 or y+oh > h+.001:
            issues.append(f"{o['name']}: 지도 경계 밖")
        if o['object_type'] == 'emergency_exit' and min(abs(x),abs(y),abs(w-x-ow),abs(h-y-oh)) > .3:
            issues.append(f"{o['name']}: 출구가 벽면에서 떨어져 있음")
    for z in design.get('zones', []):
        c = z['coordinates']
        if z['zone_type'] == 'polygon':
            pts = c.get('points', [])
        elif z['zone_type'] == 'circle':
            x,y,r = c.get('x',0),c.get('y',0),c.get('radius',0)
            pts = [dict(x=x-r,y=y-r),dict(x=x+r,y=y+r)]
        else:
            x,y = c.get('x',0),c.get('y',0)
            pts = [dict(x=x,y=y),dict(x=x+c.get('width',0),y=y+c.get('height',0))]
        if any(not 0 <= p['x'] <= w or not 0 <= p['y'] <= h for p in pts):
            issues.append(f"{z['zone_name']}: 구역이 지도 경계 밖")
    return issues
