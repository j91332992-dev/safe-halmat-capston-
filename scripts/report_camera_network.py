"""Report payload and adapter bytes separately; adapter counters include other apps."""
import json,sys
from pathlib import Path
from datetime import datetime
import numpy as np
p=Path(sys.argv[1]);rows=[json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]
rows=[r for r in rows if 'camera' in r]
t0=datetime.fromisoformat(rows[0]['at'])
rows=[r for r in rows if (datetime.fromisoformat(r['at'])-t0).total_seconds()>=15]
a,b=rows[0],rows[-1];seconds=(datetime.fromisoformat(b['at'])-datetime.fromisoformat(a['at'])).total_seconds()
c0,c1=a['camera'],b['camera']
delta=lambda k:c1.get(k,0)-c0.get(k,0)
result={'start':a['at'],'end':b['at'],'seconds':seconds,'received_fps':delta('received_frames')/seconds,
 'yolo_fps':delta('analysis_completed')/seconds,'detail_fps':delta('detail_completed')/seconds,
 'camera_jpeg_MB':delta('received_jpeg_bytes')/1e6,'camera_jpeg_MBps':delta('received_jpeg_bytes')/seconds/1e6,
 'camera_payload_Mbps':delta('received_payload_bytes')*8/seconds/1e6,
 'mean_jpeg_KB':delta('received_jpeg_bytes')/max(1,delta('received_frames'))/1000,
 'replaced_pending_frames':delta('dropped_stale_frames'),'pacing_replacements':delta('paced_skipped_frames'),
 'voice_active_samples':sum(r['camera']['voice_requests_active']>0 for r in rows),'samples':len(rows),
 'audio_WAV_KB':(c1['audio_upload']['uploaded_bytes']-c0['audio_upload']['uploaded_bytes'])/1000,
 'audio_files':c1['audio_upload']['uploaded_files']-c0['audio_upload']['uploaded_files'],'network_adapters':{}}
for name,last in b.get('network_adapters',{}).items():
    first=a.get('network_adapters',{}).get(name)
    if not first:continue
    d={k:last[k]-first[k] for k in last}
    if d['bytes_sent'] or d['bytes_recv']:
        result['network_adapters'][name]={'rx_Mbps':d['bytes_recv']*8/seconds/1e6,'tx_Mbps':d['bytes_sent']*8/seconds/1e6,
          'errors_or_drops':{k:v for k,v in d.items() if not k.startswith('bytes')}}
root=Path(__file__).resolve().parents[1];traces=[]
for log in (root/'backend/logs').glob('camera-analysis.jsonl*'):
    for s in log.read_text(encoding='utf-8').splitlines():
        try:r=json.loads(s)
        except ValueError:continue
        if a['at']<=r['at']<=b['at']:traces.append(r)
fast=[r for r in traces if r.get('lane')=='fast' and 'worker_total_ms' in r.get('analysis',{})]
if fast:
    for label,values in {'worker_ms':[r['analysis']['worker_total_ms'] for r in fast],
        'server_wait_plus_ipc_ms':[max(0,r['inference_ms']-r['analysis']['worker_total_ms']) for r in fast],
        'full_model_inference_ms':[r['analysis']['full_model_ms']['inference'] for r in fast]}.items():
        result[label+'_p50_p95']=np.percentile(values,[50,95]).tolist()
hosts=[r['host'] for r in rows if 'host' in r]
intervals=[]
for left,right in zip(rows,rows[1:]):
    dt=(datetime.fromisoformat(right['at'])-datetime.fromisoformat(left['at'])).total_seconds()
    if dt<=0:continue
    count=right['camera']['analysis_completed']-left['camera']['analysis_completed']
    intervals.append({'seconds':dt,'frames':count,'fps':count/dt,
        'voice_sampled':bool(left['camera']['voice_requests_active'] or right['camera']['voice_requests_active'])})
result['sample_interval_fps']=intervals
result['voice_sampled_interval_summary']={}
for active in (False,True):
    group=[i for i in intervals if i['voice_sampled']==active]
    if group:
        result['voice_sampled_interval_summary'][str(active)]={'fps':sum(i['frames'] for i in group)/sum(i['seconds'] for i in group),
            'seconds':sum(i['seconds'] for i in group),'intervals':len(group)}
lags=[r['camera']['event_loop_lag_ms'] for r in rows if r['camera'].get('event_loop_lag_ms',{}).get('samples')]
if lags:result['loop_lag_rolling_windows']={'largest_max_ms':max(v['max'] for v in lags),
    'p95_ms_min_max':[min(v['p95'] for v in lags),max(v['p95'] for v in lags)]}
if hosts:
    result['host']={'cpu_percent_p50_p95':np.percentile([h['cpu_percent'] for h in hosts],[50,95]).tolist(),
        'ram_used_MiB_min_max':[min(h['ram_used_bytes'] for h in hosts)/2**20,max(h['ram_used_bytes'] for h in hosts)/2**20],
        'logical_cpus':hosts[-1]['logical_cpus']}
result['server_processes']=[]
for pid in sorted({v['pid'] for r in rows for v in r.get('server_processes',[])}):
    samples=[(datetime.fromisoformat(r['at']),v) for r in rows for v in r.get('server_processes',[]) if v['pid']==pid]
    elapsed=(samples[-1][0]-samples[0][0]).total_seconds()
    if elapsed<=0:continue
    result['server_processes'].append({'pid':pid,
        'cpu_core_equivalents':(samples[-1][1]['cpu_seconds']-samples[0][1]['cpu_seconds'])/elapsed,
        'rss_MiB_min_max':[min(v['rss_bytes'] for _,v in samples)/2**20,max(v['rss_bytes'] for _,v in samples)/2**20],
        'max_threads':max(v['threads'] for _,v in samples)})
result['limitations']=['Adapter traffic includes other applications; payload bytes exclude TCP/Wi-Fi overhead.',
    'Frame replacements are latest-frame queue decisions, not measured network packet loss.',
    'CPU core equivalents: 1.0 means one logical CPU fully used; RSS can include shared pages.',
    'Live P4 heap/PSRAM and running flash image usage are not supplied by this collector.',
    'Dashboard polling itself adds load; voice-active samples do not measure acoustic response latency.']
result['limitations'].append('Voice grouping uses interval endpoint samples, not continuous voice activity; loop p95 values are overlapping rolling windows.')
out=p.with_suffix('.summary.json');out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
