import pytest
from pydantic import ValidationError
from app.services.anchor_survey_trace import STAGES,summarize_trace
from app.routers.anchor_survey import StageDiagnostic,CompleteIn


def trace(anchor,a=2,b=3,received=True,**counters):
    return dict(anchor=anchor,a=a,b=b,version=1,received=received,
                counts=[counters.get(k,0) for k in STAGES],last_status=0,last_function=0,last_distance=None)


def findings(rows):
    return next(p for p in summarize_trace(rows)['pairs'] if p['pair']=='2-3')


def test_missing_report_is_unknown_not_a_slot_failure():
    r=findings([trace(1,slot_tx=16),trace(2,received=False),trace(3)])
    assert r['missing_reports']==['initiator']
    assert r['findings']==['diagnostic_report_missing']


def test_slot_and_poll_boundaries_are_separate():
    r=findings([trace(1,slot_tx=16),trace(2),trace(3)])
    assert 'slot_not_received' in r['findings']
    r=findings([trace(1,slot_tx=16),trace(2,slot_rx=16,poll_tx=16,rx_timeout=16),trace(3)])
    assert 'slot_not_received' not in r['findings']
    assert 'poll_not_observed_by_responder' in r['findings']
    assert 'initiator_rx_timeout' in r['findings']


def test_relay_loss_is_not_reported_as_ranging_failure():
    r=findings([trace(1,slot_tx=16,relay_rx=0),trace(2,slot_rx=16,poll_tx=16,distance_ok=16,relay_tx=16),
                trace(3,attempt=16,final_rx=16)])
    assert r['findings']==['relay_reports_missing_at_coordinator']


def test_wire_counters_preserve_version_order():
    t=StageDiagnostic.model_validate(trace(2,slot_rx=16,interval_error=3))
    r=summarize_trace([t.model_dump()])['records'][0]
    assert r['counters']['slot_rx']==16 and r['counters']['interval_error']==3


@pytest.mark.parametrize('patch',[dict(counts=[0]*23),dict(counts=[256]*24),dict(a=3,b=2),dict(anchor=4)])
def test_invalid_wire_values_rejected(patch):
    with pytest.raises(ValidationError):StageDiagnostic.model_validate(dict(trace(2),**patch))


def test_legacy_result_and_duplicate_record_validation():
    payload=dict(nonce='n',completed=True,duration_ms=10000,samples=[])
    assert CompleteIn.model_validate(payload).stage_diagnostics==[]
    with pytest.raises(ValidationError):
        CompleteIn.model_validate(dict(payload,stage_diagnostics=[trace(2),trace(2)]))
