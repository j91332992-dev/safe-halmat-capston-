"""Merge only fresh, spatially matching PPE evidence; never copy old boxes."""
def person_box(analysis):
    if analysis.get('person_seen') is False:
        return None
    people=[d for d in analysis.get('detections',[]) if d.get('category')=='person' and d.get('positive',True)]
    return max(people,key=lambda d:d['confidence'])['box'] if len(people)==1 else None

def overlap(a,b):
    intersection=max(0,min(a['x2'],b['x2'])-max(a['x1'],b['x1']))*max(0,min(a['y2'],b['y2'])-max(a['y1'],b['y1']))
    area=lambda v:max(0,v['x2']-v['x1'])*max(0,v['y2']-v['y1'])
    return intersection/max(1,area(a)+area(b)-intersection)

def merge_detail(analysis, cached, now, max_age):
    current=person_box(analysis)
    valid=False
    age=None
    if cached:
        age=now-cached['submitted_at']
        previous=person_box(cached['analysis'])
        valid=age<=max_age and current is not None and previous is not None and overlap(current,previous)>=.5
    # Fast-frame non-detection is not evidence of missing PPE between detail jobs.
    observed={k:any(d.get('category')==k and d.get('positive',True) for d in analysis.get('detections',[])) for k in ('helmet','vest','glove')}
    analysis['ppe']={k:True if current and observed[k] else (cached['analysis'].get('ppe',{}).get(k) if valid else None) for k in observed}
    analysis['ppe_judgement']={**(cached['analysis'].get('ppe_judgement',{}) if valid else {}),
        'status':'fresh_detail' if valid else 'awaiting_detail', 'active':valid,
        'subject_scope':'observed_person','detail_frame_id':cached['frame_id'] if valid else None,
        'detail_age_ms':round(age*1000,1) if age is not None else None}
    analysis['detail_evidence']={'valid':valid,'age_ms':round(age*1000,1) if age is not None else None,
        'frame_id':cached['frame_id'] if cached else None,
        'detections':cached['analysis'].get('detections',[]) if valid else []}
    return analysis
