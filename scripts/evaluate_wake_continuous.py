"""Diagnostic concatenation of held-out clips; synthetic gaps are not real background."""
import argparse
import json
from pathlib import Path
import random
import wave
import numpy as np
from ai_edge_litert.interpreter import Interpreter
from microwakeword.audio.audio_utils import generate_features_for_clip

p=argparse.ArgumentParser()
p.add_argument('--model',type=Path,required=True)
p.add_argument('--manifest',type=Path,required=True)
p.add_argument('--data',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
files=[r for r in json.loads(a.manifest.read_text())['files'] if r['split']=='testing']
random.Random(20261016).shuffle(files)
audio=[np.zeros(32000,dtype=np.int16)]; cursor=32000; segments=[]
for row in files:
    with wave.open(str(a.data/row['file']),'rb') as w:
        x=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2')
    segments.append({**row,'start_s':cursor/16000,'clip_end_s':(cursor+len(x))/16000,
                     'analysis_end_s':(cursor+len(x)+16000)/16000,'peak':0,'candidate_count':0})
    audio.extend([x,np.zeros(32000,dtype=np.int16)]);cursor+=len(x)+32000
features=generate_features_for_clip(np.concatenate(audio),step_ms=10)
i=Interpreter(model_path=str(a.model),num_threads=1);i.allocate_tensors()
inp=i.get_input_details()[0];out=i.get_output_details()[0]
scale,zero=inp['quantization'];oscale,ozero=out['quantization']
events=[];last_event=-100;quiet_events=0
for end in range(3,len(features)+1,3):
    q=np.clip(features[end-3:end]/scale+zero,-128,127).astype(np.int8)
    i.set_tensor(inp['index'],q.reshape(inp['shape']));i.invoke()
    score=(int(i.get_tensor(out['index']).flat[0])-ozero)*oscale
    # Frame 1 is available after a 30ms window; subsequent features every10ms.
    ts=.02+end*.01
    segment=next((r for r in segments if r['start_s']<=ts<r['analysis_end_s']),None)
    if segment:segment['peak']=max(segment['peak'],score)
    if ts>=1.5 and score>=.7 and ts-last_event>2:
        last_event=ts
        events.append(dict(time_s=ts,score=score,file=segment['file'] if segment else None))
        if segment:segment['candidate_count']+=1
        else:quiet_events+=1
result=dict(warning='Post-hoc synthetic continuity probe. Clip end is not keyword end; no real background or device latency measured.',
            threshold=.7,seconds=cursor/16000,quiet_events=quiet_events,segments=segments,events=events)
a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(dict(positive_hits=sum(r['candidate_count']>0 for r in segments if r['label']=='positive'),
    negative_hits=sum(r['candidate_count']>0 for r in segments if r['label']=='negative'),quiet_events=quiet_events)))
