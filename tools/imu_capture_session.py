"""Post-flash wireless IMU capture + concurrent subsystem diagnostics.

Uses existing administrator credentials via env or getpass; never writes tokens.
Raw IMU remains on the backend; this local helper archives it after capture.
"""
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import sys
import time

import requests


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['status','baseline','capture'])
    parser.add_argument('--server',default='http://127.0.0.1:8000')
    parser.add_argument('--username',default='TUTUS')
    parser.add_argument('--device',default='helmet-001-av')
    parser.add_argument('--seconds',type=int,default=600)
    parser.add_argument('--output',type=Path,default=Path('C:/dev/hanmir-runtime/imu-full-capture'))
    args=parser.parse_args()
    if not 1<=args.seconds<=1800:parser.error('--seconds must be 1..1800')
    password=os.environ.pop('HANMIR_MONITOR_PASSWORD','') or getpass.getpass('관리자 비밀번호: ')
    session=requests.Session()
    response=session.post(args.server+'/api/auth/login',json={'username':args.username,'password':password},timeout=10)
    response.raise_for_status();session.headers['Authorization']='Bearer '+response.json()['token']

    def api(path,body=None):
        response=session.get(args.server+path,timeout=8) if body is None else session.post(args.server+path,json=body,timeout=8)
        if not response.ok:
            try:detail=response.json().get('detail','')
            except ValueError:detail=''
            raise RuntimeError(f'HTTP {response.status_code}: {detail}')
        return response.json()

    prefix='/api/imu/'+args.device
    state=api(prefix+'/status')
    if args.action=='status':print(json.dumps(state,ensure_ascii=False,indent=2));return
    if args.action=='baseline':
        old_live=state.get('live') or {}
        old_metrics=old_live.get('metrics',{}) if old_live.get('age_ms',99999)<2000 else state.get('heartbeat') or {}
        old_generation=old_metrics.get('baseline_generation',0)
        print(json.dumps(api(prefix+'/baseline',{}),ensure_ascii=False,indent=2))
        print('정상 직립·착용 상태를 직접 유지하세요. 1초 안정 입력 후 baseline_ready=true가 되어야 완료입니다.')
        for _ in range(15):
            time.sleep(2);s=api(prefix+'/status')
            live=s.get('live')
            metrics=live['metrics'] if live and live.get('age_ms',99999)<2000 else s.get('heartbeat') or {}
            if (metrics.get('baseline_ready') and not metrics.get('calibration_pending') and
                    metrics.get('baseline_generation',0)>old_generation):
                print('기준 자세 저장 완료');return
        raise RuntimeError('기준 저장 완료를 확인하지 못했습니다. 센서 상태·수신 주기를 확인하세요.')

    folder=args.output.resolve()/datetime.now().strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True,exist_ok=False)
    started=time.time(); deadline=time.monotonic()+args.seconds
    before=api(prefix+'/status')
    api(prefix+'/capture',dict(enabled=True,duration_s=args.seconds))
    metadata=dict(started_at=datetime.now(timezone.utc).isoformat(),device=args.device,
        requested_seconds=args.seconds,initial_status=before,
        limitations=['P4 candidates are local shadow reports; server confirmation/TTS/admin alerts may be enabled (see initial_status.confirmation).',
            'USB/power configuration must be recorded separately before estimating battery consumption.',
            'Network export is lossy if device/server diagnostic counters increase.'])
    (folder/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    print('기록 폴더:',folder,flush=True)
    previous=None;sample_count=0
    try:
        with (folder/'subsystems.jsonl').open('w',encoding='utf-8') as output:
            while time.monotonic()<deadline:
                sample={'at':datetime.now(timezone.utc).isoformat(),'elapsed_s':time.time()-started}
                for name,path in [('imu',prefix+'/status'),('camera','/api/camera/processor/status'),
                    ('call',f'/api/calls/{args.device}/status'),('devices','/api/diagnostics/devices')]:
                    began=time.monotonic()
                    try:sample[name]=api(path)
                    except Exception as exc:sample[name]={'error':type(exc).__name__}
                    sample[name+'_request_ms']=round((time.monotonic()-began)*1000,2)
                output.write(json.dumps(sample,ensure_ascii=False)+'\n');output.flush();sample_count+=1
                imu=sample.get('imu',{});live=imu.get('live') or {};metrics=live.get('metrics',{})
                camera=sample.get('camera',{});fps=None
                if previous and 'analysis_completed' in camera and 'analysis_completed' in previous.get('camera',{}):
                    dt=sample['elapsed_s']-previous['elapsed_s']
                    fps=(camera['analysis_completed']-previous['camera']['analysis_completed'])/max(dt,.001)
                print(json.dumps(dict(seconds=round(sample['elapsed_s']),imu_age_ms=live.get('age_ms'),
                    yolo_fps=None if fps is None else round(fps,2),heap_free=metrics.get('heap_free'),
                    capture_overflow=metrics.get('telemetry_overflow'),sequence_gaps=live.get('batch_sequence_missing'),
                    impact=metrics.get('impact_candidates'),posture=metrics.get('posture_candidates')),
                    ensure_ascii=False),flush=True)
                previous=sample
                time.sleep(max(0,min(2,deadline-time.monotonic())))
    finally:
        try:api(prefix+'/capture',dict(enabled=False,duration_s=args.seconds))
        except Exception:pass
        try:final=api(prefix+'/status')
        except Exception as exc:final={'error':type(exc).__name__,'note':'Final status unavailable; subsystem samples retained.'}
        (folder/'final_status.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8')
        # Local server logs only. A remote server must export its own files.
        source=Path(final.get('log',{}).get('path',''))
        if source.is_file() and args.server in ('http://127.0.0.1:8000','http://localhost:8000'):
            sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
            from scripts.shared_log_reader import shared_binary_reader
            exported=0
            time.sleep(.5)
            with (folder/'imu-raw.jsonl').open('wb') as dest:
                for path in [Path(str(source)+'.'+str(n)) for n in range(4,0,-1)]+[source]:
                    if not path.is_file():continue
                    with shared_binary_reader(path) as raw:
                        for line in raw:
                            try:r=json.loads(line)
                            except ValueError:continue
                            if r.get('device_id')==args.device and r.get('logged_at_unix',0)>=started:
                                dest.write(line);exported+=1
            print('원본 IMU 묶음 내보냄:',exported)
        print('상태 샘플:',sample_count,'자동 경보 없이 기록 종료')


if __name__=='__main__':main()
