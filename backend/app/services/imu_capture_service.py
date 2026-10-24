"""IMU diagnostic ingestion: bounded memory/disk, no per-sample DB or alarm calls."""
import atexit
from datetime import datetime, timezone
import math
from pathlib import Path
from queue import Queue, Full
from threading import Lock, Thread
from time import monotonic

from ..config import BASE_DIR
from .uwb_log_service import BoundedJsonlLog

_queue=Queue(maxsize=128)
_thread=None
_lock=Lock()
_latest={}
_stats=dict(enqueued=0,written=0,overflow_batches=0,write_errors=0,rotation_blocked=0,invalid_batches=0)


def rejected():
    _stats['invalid_batches']+=1


def _writer():
    log=None
    while True:
        item=_queue.get()
        try:
            if item is None:return
            if log is None:
                log=BoundedJsonlLog(BASE_DIR/'logs'/'imu-capture.jsonl',
                    max_bytes=20*1024*1024,backups=4,retention_days=7,expiry_check_seconds=60)
            log.append(item)
            _stats['written']+=1
            _stats['rotation_blocked']=log.rotation_blocked
        except Exception:
            _stats['write_errors']+=1
        finally:_queue.task_done()


def _close():
    if _thread and _thread.is_alive():
        try:_queue.put_nowait(None)
        except Full:return
        _thread.join(timeout=3)


atexit.register(_close)


def validate_batch(packet):
    if not isinstance(packet,dict) or packet.get('type')!='imu_batch' or packet.get('v')!=1:
        raise ValueError('unsupported IMU packet')
    boot=packet.get('boot')
    if not isinstance(boot,str) or len(boot)!=8 or any(c not in '0123456789abcdef' for c in boot):
        raise ValueError('invalid boot ID')
    for key in ('batch','tx_us'):
        if type(packet.get(key)) is not int or not 0<=packet[key]<=2**53-1:
            raise ValueError('invalid packet counter')
    records=packet.get('records')
    if not isinstance(records,list) or not 1<=len(records)<=16:raise ValueError('invalid batch size')
    for record in records:
        if not isinstance(record,list) or len(record)!=9:raise ValueError('invalid IMU row')
        if any(type(v) is not int for v in record[:5]):raise ValueError('invalid IMU header')
        kind,sequence,status,sensor_us,received_us=record[:5]
        if kind not in (1,2,5,8,100,101,200,201) or not 0<=sequence<=255 or not 0<=status<=3:
            raise ValueError('invalid report metadata')
        if not 0<=sensor_us<=2**53-1 or not 0<=received_us<=packet['tx_us']:
            raise ValueError('invalid IMU timestamp')
        if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e6 for v in record[5:]):
            raise ValueError('invalid IMU value')
    metrics=packet.get('metrics',{})
    if not isinstance(metrics,dict) or len(metrics)>50:raise ValueError('invalid metrics')
    if metrics.get('fall_mode')!='shadow':raise ValueError('unexpected fall mode')
    return packet


def ingest(device_id,site_id,packet,wire_bytes):
    global _thread
    now=monotonic()
    previous=_latest.get(device_id)
    same_boot=previous and previous['boot']==packet['boot']
    missing=(max(0,packet['batch']-previous['batch']-1) if same_boot else 0)
    counters={kind:sum(r[0]==kind for r in packet['records']) for kind in (1,2,5,8,100,101)}
    seen=list(previous.get('_candidate_seen',[])) if same_boot else []
    unique=[]
    for row in packet['records']:
        key=(row[0],row[3])
        if row[0] in (100,101) and key not in seen:
            unique.append(row);seen.append(key)
    seen=seen[-64:]
    status=dict(device_id=device_id,site_id=site_id,boot=packet['boot'],batch=packet['batch'],
        received_at=datetime.now(timezone.utc).isoformat(),received_mono=now,
        batches=(previous['batches'] if same_boot else 0)+1,
        records=(previous['records'] if same_boot else 0)+len(packet['records']),
        wire_bytes=(previous['wire_bytes'] if same_boot else 0)+wire_bytes,
        batch_sequence_missing=(previous['batch_sequence_missing'] if same_boot else 0)+missing,
        max_receive_gap_ms=max(previous['max_receive_gap_ms'],(now-previous['received_mono'])*1000) if same_boot else 0,
        counts={str(k):(previous['counts'].get(str(k),0) if same_boot else 0)+n for k,n in counters.items()},
        metrics=packet.get('metrics',{}),last_records=packet['records'],
        _candidate_seen=seen,unique_candidates=unique,
        unique_candidate_count=(previous.get('unique_candidate_count',0) if same_boot else 0)+len(unique))
    if len(_latest)>=256 and device_id not in _latest:
        del _latest[min(_latest,key=lambda k:_latest[k]['received_mono'])]
    _latest[device_id]=status
    with _lock:
        if _thread is None:
            _thread=Thread(target=_writer,name='imu-capture-writer',daemon=True);_thread.start()
    try:
        _queue.put_nowait(dict(at=status['received_at'],device_id=device_id,site_id=site_id,
                            wire_bytes=wire_bytes,packet=packet))
        _stats['enqueued']+=1
    except Full:_stats['overflow_batches']+=1
    return status


def snapshot(device_id):
    value=_latest.get(device_id)
    return None if value is None else {**{k:v for k,v in value.items() if k!='received_mono' and not k.startswith('_')},
                                     'age_ms':round((monotonic()-value['received_mono'])*1000,1)}


def log_status():
    return {**_stats,'queue_depth':_queue.qsize(),'capacity':128,
            'path':str(Path(BASE_DIR)/'logs'/'imu-capture.jsonl'),
            'max_file_bytes':20*1024*1024,'backups':4,'retention_days':7}
