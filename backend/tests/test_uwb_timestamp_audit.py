import pytest

from app.services.uwb_timestamp_audit import METERS_PER_DTU,audit_timestamp


def capture(clock=0,tx=1000,remote_rx=2000,distance=5.2):
    reply=196608000
    round_trip=round(reply*(1-clock/67108864.0)+2*distance/METERS_PER_DTU)
    return dict(poll_tx_dtu_low32=tx,response_rx_dtu_low32=(tx+round_trip)&0xffffffff,
        remote_poll_rx_dtu_low32=remote_rx,remote_response_tx_dtu_low32=(remote_rx+reply)&0xffffffff,
        clock_offset_raw=clock,sys_status=0x4400,distance_m=distance)


@pytest.mark.parametrize('clock',[-64,0,64])
def test_clock_sign_scale_and_distance(clock):
    result=audit_timestamp(capture(clock=clock))
    assert result['status']=='match'
    assert abs(result['recomputed_m']-5.2)<.003
    assert result['clock_ppm']==pytest.approx(clock*1e6/67108864.0)


def test_timestamp_wrap_is_unsigned_modulo_32():
    result=audit_timestamp(capture(clock=64,tx=0xfffffff0,remote_rx=0xffffff00))
    assert result['status']=='match'
    assert result['reply_delay_dtu']==196608000


def test_wrong_reported_distance_is_detected_without_fixing_it():
    sample=capture();sample['distance_m']+=.4
    result=audit_timestamp(sample)
    assert result['status']=='mismatch'
    assert sample['distance_m']==pytest.approx(5.6)


def test_legacy_samples_and_partial_capture_are_distinguished():
    assert audit_timestamp({'distance_m':5.2})['status']=='unavailable'
    assert audit_timestamp({'distance_m':5.2,'clock_offset_raw':0})['status']=='incomplete'


@pytest.mark.parametrize('status',[0x4000,0x4400|(1<<18)])
def test_cia_must_be_done_and_error_free(status):
    sample=capture();sample['sys_status']=status
    assert audit_timestamp(sample)['status']=='invalid_cia'


def test_reversed_or_zero_reply_interval_is_rejected():
    sample=capture();sample['remote_response_tx_dtu_low32']=sample['remote_poll_rx_dtu_low32']
    assert audit_timestamp(sample)['status']=='invalid_intervals'


@pytest.mark.parametrize('local_ppm,remote_ppm',[(0,0),(10,-10),(-10,10),(5,0)])
def test_double_sided_math_cancels_relative_clock_error(local_ppm,remote_ppm):
    tof=5.2/METERS_PER_DTU;db=180000000;da=220000000
    local=lambda t:(0xfffffff0+round(t*(1+local_ppm*1e-6)))&0xffffffff
    remote=lambda t:(0xffffff00+round(t*(1+remote_ppm*1e-6)))&0xffffffff
    s=dict(ranging_method='ds-twr',poll_tx_dtu_low32=local(0),
        response_rx_dtu_low32=local(2*tof+db),final_tx_dtu_low32=local(2*tof+db+da),
        remote_poll_rx_dtu_low32=remote(tof),remote_response_tx_dtu_low32=remote(tof+db),
        remote_final_rx_dtu_low32=remote(3*tof+db+da),clock_offset_raw=0,sys_status=0x4400,distance_m=5.2)
    result=audit_timestamp(s)
    assert result['status']=='match'
    assert abs(result['recomputed_m']-5.2)<.005
    assert result['clock_correction_m']==0


def test_double_sided_sample_requires_final_timestamps():
    sample=capture();sample['ranging_method']='ds-twr'
    assert audit_timestamp(sample)['status']=='incomplete'
