"""Audit SS/DS-TWR arithmetic without applying room-size or learned offsets."""
import math

METERS_PER_DTU = 299702547.0 / (499.2e6 * 128.0)
RAW_FIELDS = ('poll_tx_dtu_low32','response_rx_dtu_low32',
              'remote_poll_rx_dtu_low32','remote_response_tx_dtu_low32',
              'clock_offset_raw','sys_status')


def audit_timestamp(sample):
    values = [sample.get(k) for k in RAW_FIELDS]
    if all(v is None for v in values):
        return {'status':'unavailable'}
    if any(v is None for v in values):
        return {'status':'incomplete'}
    tx,rx,remote_rx,remote_tx,clock,status = values
    if not status & 0x400 or status & (1 << 18):
        return {'status':'invalid_cia'}
    round_trip = (rx-tx) & 0xffffffff
    reply = (remote_tx-remote_rx) & 0xffffffff
    if not 0 < round_trip < 0x80000000 or not 0 < reply < 0x80000000:
        return {'status':'invalid_intervals'}
    uncorrected = (round_trip-reply)*.5*METERS_PER_DTU
    ss = (round_trip-reply*(1.0-clock/67108864.0))*.5*METERS_PER_DTU
    method=sample.get('ranging_method') or 'ss-twr'
    corrected=ss
    if method=='ds-twr':
        final_tx=sample.get('final_tx_dtu_low32');remote_final_rx=sample.get('remote_final_rx_dtu_low32')
        if final_tx is None or remote_final_rx is None:
            return {'status':'incomplete'}
        da=(final_tx-rx)&0xffffffff
        rb=(remote_final_rx-remote_tx)&0xffffffff
        if not 0<da<0x80000000 or not 0<rb<0x80000000:
            return {'status':'invalid_intervals'}
        corrected=(round_trip*rb-da*reply)/(round_trip+rb+da+reply)*METERS_PER_DTU
    elif method!='ss-twr':
        return {'status':'unsupported_method'}
    delta = corrected-sample['distance_m']
    return dict(status='match' if math.isfinite(delta) and abs(delta)<=.005 else 'mismatch',
        round_trip_dtu=round_trip,reply_delay_dtu=reply,clock_ppm=clock*1e6/67108864.0,
        uncorrected_m=uncorrected,recomputed_m=corrected,
        ranging_method=method,clock_correction_m=ss-uncorrected if method=='ss-twr' else 0.0,
        ss_comparison_m=ss,ds_vs_ss_m=corrected-ss if method=='ds-twr' else None,reported_delta_m=delta)
