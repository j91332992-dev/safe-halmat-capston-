"""Read camera/device counters while wake testing. Credentials only via environment."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
import urllib.request
import psutil

p=argparse.ArgumentParser();p.add_argument('--base',default='http://127.0.0.1:8000')
p.add_argument('--seconds',type=int,default=180);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
if not 1<=a.seconds<=600:p.error('seconds must be 1..600')
if a.output.exists():p.error('Use a new output file')
body=json.dumps({'username':os.environ['HANMIR_TEST_USER'],'password':os.environ['HANMIR_TEST_PASSWORD']}).encode()
r=json.load(urllib.request.urlopen(urllib.request.Request(a.base+'/api/auth/login',data=body,headers={'Content-Type':'application/json'}),timeout=5))
token=r.get('access_token') or r.get('token')
def get(path):
    return json.load(urllib.request.urlopen(urllib.request.Request(a.base+path,headers={'Authorization':'Bearer '+token}),timeout=3))
a.output.parent.mkdir(parents=True,exist_ok=True)
end=time.monotonic()+a.seconds
tracked={}
roots={}
for process in psutil.process_iter(['pid','name','cmdline']):
    try:
        args=process.info['cmdline'] or []
        if 'uvicorn' in args and 'app.main:app' in args:
            roots[process.pid]=process
            for candidate in [process,*process.children(recursive=True)]:
                if 'python' in candidate.name().lower():tracked[candidate.pid]=candidate
    except (psutil.Error,OSError):pass
with a.output.open('w',encoding='utf-8') as f:
    while time.monotonic()<end:
        # Workers are spawned lazily after the first frame; discover them too.
        for process in roots.values():
            try:
                for child in process.children(recursive=True):
                    if 'python' in child.name().lower():tracked[child.pid]=child
            except psutil.Error:pass
        row={'at':datetime.now(timezone.utc).isoformat()}
        row['network_adapters']={name:{'bytes_sent':v.bytes_sent,'bytes_recv':v.bytes_recv,'dropin':v.dropin,'dropout':v.dropout,'errin':v.errin,'errout':v.errout} for name,v in psutil.net_io_counters(pernic=True).items()}
        memory=psutil.virtual_memory()
        row['host']={'logical_cpus':psutil.cpu_count(),'cpu_percent':psutil.cpu_percent(),'ram_used_bytes':memory.used,'ram_available_bytes':memory.available}
        row['server_processes']=[]
        for pid,process in tracked.items():
            try:
                cpu=process.cpu_times();mem=process.memory_info()
                row['server_processes'].append({'pid':pid,'cpu_seconds':cpu.user+cpu.system,'rss_bytes':mem.rss,'threads':process.num_threads()})
            except psutil.Error:pass
        try:
            row['camera']=get('/api/camera/processor/status')
            row['devices']=[{k:d.get(k) for k in ('device_id','online','last_seen','last_camera_at','last_audio_at','heading_at','last_uwb_at','rssi','component_status')}
                            for d in get('/api/dashboard/snapshot')['devices']]
        except Exception as e:row['error_type']=type(e).__name__
        f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush()
        time.sleep(min(2,max(0,end-time.monotonic())))
print('Metrics saved')
