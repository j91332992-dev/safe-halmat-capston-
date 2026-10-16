"""Summarize instrumented UART intervals, not keyword accuracy or acoustic latency."""
import argparse
import json
import re
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('trace',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
stats=[];candidates=[];errors=[]
for line in a.trace.read_text(encoding='utf-8').splitlines():
    row=json.loads(line);message=row['line']
    if 'tutus_shadow:' not in message:continue
    values={k:float(v) for k,v in re.findall(r'([a-z_]+)=(-?\d+(?:\.\d+)?)',message)}
    if 'stats invokes=' in message:stats.append(dict(host_received_at=row['host_received_at'],**values))
    if 'CANDIDATE' in message:candidates.append(dict(host_received_at=row['host_received_at'],**values))
    if any(s in message for s in ('failed','PCM gap')):errors.append(row)
def high(key):return max((r[key] for r in stats if key in r),default=None)
def low(key):return min((r[key] for r in stats if key in r),default=None)
result=dict(intervals=len(stats),inferences_in_logged_intervals=sum(int(r['invokes']) for r in stats),
    processing_max_us=high('processing_max_us'),queue_max_us=high('queue_max_us'),
    cumulative_drop_counter=high('drops'),cumulative_deadline_miss_counter=high('deadline_misses'),
    minimum_internal_free_bytes=low('heap_internal'),boot_minimum_internal_free_bytes=low('heap_min'),
    minimum_task_stack_free_bytes=low('stack_free_min'),candidates=candidates,errors=errors,
    limitation='Interval maxima, not per-inference timing distribution. Candidate is not verified recognition. No keyword-end/acoustic response latency measured.')
a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
