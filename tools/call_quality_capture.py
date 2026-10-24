"""Capture call metrics without enabling high-rate IMU raw export."""
import argparse,getpass,json,os,time
from datetime import datetime,timezone
from pathlib import Path
import requests

def main():
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=int,default=180);p.add_argument('--device',default='helmet-001-av');p.add_argument('--server',default='http://127.0.0.1:8000');args=p.parse_args()
    if not 1<=args.seconds<=1800:p.error('seconds must be 1..1800')
    password=os.environ.pop('HANMIR_MONITOR_PASSWORD','') or getpass.getpass('관리자 비밀번호: ')
    s=requests.Session();r=s.post(args.server+'/api/auth/login',json={'username':'TUTUS','password':password},timeout=10);r.raise_for_status();s.headers['Authorization']='Bearer '+r.json()['token']
    folder=Path('C:/dev/hanmir-runtime/call-quality-20261024')/datetime.now().strftime('%Y%m%d-%H%M%S');folder.mkdir(parents=True)
    (folder/'metadata.json').write_text(json.dumps({'started_at':datetime.now(timezone.utc).isoformat(),'device':args.device,'requested_seconds':args.seconds,'imu_raw_export_enabled_by_collector':False,'limitation':'Counters and hearing feedback do not establish acoustic quality without a paired recording.'},indent=2),encoding='utf-8')
    end=time.monotonic()+args.seconds;start=time.monotonic()
    print(str(folder),flush=True)
    with (folder/'samples.jsonl').open('w',encoding='utf-8') as f:
        while time.monotonic()<end:
            row={'at':datetime.now(timezone.utc).isoformat(),'elapsed_s':time.monotonic()-start}
            for name,path in [('call','/api/calls/'+args.device+'/status'),('camera','/api/camera/processor/status'),('devices','/api/diagnostics/devices')]:
                try:
                    r=s.get(args.server+path,timeout=8);r.raise_for_status();row[name]=r.json()
                except Exception as exc:row[name]={'error':type(exc).__name__}
            f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
            c=row['call'];print(json.dumps({'s':round(row['elapsed_s']),'connected':c.get('operator_connected'),'browser_audio':c.get('browser_audio')},ensure_ascii=True),flush=True)
            time.sleep(min(2,max(0,end-time.monotonic())))
    print('capture complete',flush=True)

if __name__=='__main__':main()
