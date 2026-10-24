"""Read-only zone/camera/call/memory telemetry capture; no synthetic location input."""
import argparse
import getpass
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds',type=int,default=90)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 1800: parser.error('seconds must be 1..1800')
    password = os.environ.pop('HANMIR_MONITOR_PASSWORD','') or getpass.getpass('관리자 비밀번호: ')
    session = requests.Session()
    base = 'http://127.0.0.1:8000'
    response = session.post(base+'/api/auth/login',json=dict(username='TUTUS',password=password),timeout=10)
    response.raise_for_status()
    session.headers['Authorization'] = 'Bearer '+response.json()['token']
    folder = Path('C:/dev/hanmir-runtime/zone-warning-20261024')/datetime.now().strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True)
    print(folder,flush=True)
    started = time.monotonic()
    paths = dict(zone='/api/zones/warnings/status',camera='/api/camera/processor/status',
        devices='/api/diagnostics/devices',location='/api/locations/worker-001/latest',
        call='/api/calls/helmet-001-av/status')
    with (folder/'samples.jsonl').open('w',encoding='utf-8') as output:
        while time.monotonic()-started < args.seconds:
            row = dict(at=datetime.now(timezone.utc).isoformat(),elapsed_s=time.monotonic()-started)
            for key,path in paths.items():
                try:
                    response = session.get(base+path,timeout=5)
                    response.raise_for_status()
                    row[key] = response.json()
                except Exception as exc: row[key] = dict(error=type(exc).__name__)
            output.write(json.dumps(row,ensure_ascii=False)+'\n'); output.flush()
            time.sleep(min(2,max(0,args.seconds-(time.monotonic()-started))))
    print('capture complete',flush=True)


if __name__ == '__main__': main()
