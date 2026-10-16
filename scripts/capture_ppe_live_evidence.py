"""Capture current known-worn scene; images/analysis are adjacent, not atomic."""
import argparse,json,os,time,urllib.request
from pathlib import Path
from datetime import datetime,timezone
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--seconds',type=int,default=30);p.add_argument('--no-vest',action='store_true');a=p.parse_args()
a.output.mkdir(exist_ok=False)
base='http://127.0.0.1:8000'
body=json.dumps({'username':os.environ['HANMIR_TEST_USER'],'password':os.environ['HANMIR_TEST_PASSWORD']}).encode()
auth=json.load(urllib.request.urlopen(urllib.request.Request(base+'/api/auth/login',data=body,headers={'Content-Type':'application/json'})))
headers={'Authorization':'Bearer '+(auth.get('token') or auth['access_token'])}
def get(path):return urllib.request.urlopen(urllib.request.Request(base+path,headers=headers),timeout=5).read()
end=time.monotonic()+a.seconds;n=0
with (a.output/'observations.jsonl').open('w',encoding='utf-8') as f:
 while time.monotonic()<end:
  row={'at':datetime.now(timezone.utc).isoformat(),'truth':{'helmet':True,'vest':not a.no_vest,'glove':True},'truth_source':'user report; verify visibility in images',
       'analysis':json.loads(get('/api/camera/helmet-001-av/latest')),
       'live_before':json.loads(get('/api/camera/helmet-001-av/live'))}
  (a.output/f'raw-{n:03d}.jpg').write_bytes(get('/api/camera/helmet-001-av/live/image'))
  row['live_after']=json.loads(get('/api/camera/helmet-001-av/live'))
  f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();n+=1;time.sleep(.5)
print('Saved samples:',n)
