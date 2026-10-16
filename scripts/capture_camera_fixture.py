"""Capture local raw camera evidence. Credentials via environment only."""
import os,json,time,urllib.request
import argparse
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--output',default='C:/dev/hanmir-runtime/camera-split-fixture')
p.add_argument('--count',type=int,default=8)
p.add_argument('--interval',type=float,default=.7)
a=p.parse_args();out=Path(a.output);out.mkdir(exist_ok=True)
if any(out.glob('raw-*.jpg')):raise SystemExit('Refusing to overwrite existing evidence')
base='http://127.0.0.1:8000'
body=json.dumps(dict(username=os.environ['HANMIR_TEST_USER'],password=os.environ['HANMIR_TEST_PASSWORD'])).encode()
auth=json.load(urllib.request.urlopen(urllib.request.Request(base+'/api/auth/login',data=body,headers={'Content-Type':'application/json'})))
headers={'Authorization':'Bearer '+(auth.get('access_token') or auth['token'])}
for n in range(a.count):
    data=urllib.request.urlopen(urllib.request.Request(base+'/api/camera/helmet-001-av/live/image',headers=headers),timeout=5).read()
    (out/f'raw-{n:02d}.jpg').write_bytes(data)
    time.sleep(a.interval)
print('Saved',a.count,'raw frames:',out)
