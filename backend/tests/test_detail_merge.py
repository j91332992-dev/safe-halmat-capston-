from app.services.detail_merge import merge_detail

def frame(x=0):
    return {'detections':[{'category':'person','positive':True,'confidence':.9,
                          'box':dict(x1=x,y1=0,x2=x+100,y2=200)}],
            'ppe':dict(helmet=False,vest=False,glove=False)}

def test_no_detail_is_unknown_not_missing():
    result=merge_detail(frame(),None,10,1.5)
    assert all(v is None for v in result['ppe'].values())

def test_fresh_same_person_uses_detail_without_old_boxes():
    previous=frame();previous['ppe']['helmet']=True
    result=merge_detail(frame(),dict(analysis=previous,frame_id=4,submitted_at=9),10,1.5)
    assert result['ppe']['helmet'] is True
    assert len(result['detections'])==1
    assert result['detail_evidence']['valid']

def test_expired_or_spatially_different_is_unknown():
    previous=frame();previous['ppe']['helmet']=True
    cached=dict(analysis=previous,frame_id=4,submitted_at=9)
    assert merge_detail(frame(),cached,11,1.5)['ppe']['helmet'] is None
    assert merge_detail(frame(200),cached,10,1.5)['ppe']['helmet'] is None

def test_current_positive_overrides_older_negative():
    current=frame();current['detections'].append(dict(category='helmet',positive=True,confidence=.8))
    assert merge_detail(current,dict(analysis=frame(),frame_id=4,submitted_at=9),10,1.5)['ppe']['helmet'] is True

def test_unconfirmed_person_cannot_receive_previous_ppe():
    current=frame();current['person_seen']=False
    previous=frame();previous['ppe']['helmet']=True
    assert merge_detail(current,dict(analysis=previous,frame_id=4,submitted_at=9),10,1.5)['ppe']['helmet'] is None
