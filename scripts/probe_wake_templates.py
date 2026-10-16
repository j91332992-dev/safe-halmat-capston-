"""Offline feasibility probe only. STT candidates are not ground-truth labels."""
import argparse
import json
import time
import wave
from pathlib import Path
import numpy as np


def features(path):
    with wave.open(str(path), "rb") as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (16000, 1, 2)
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768
    if len(x) < 400:
        return None
    frames = np.lib.stride_tricks.sliding_window_view(x, 400)[::160]
    energy = np.sqrt(np.mean(frames * frames, axis=1))
    active = np.flatnonzero(energy > max(.002, energy.max() * .12))
    if not len(active):
        return None
    frames = frames[max(0, active[0]-2):active[-1]+3]
    power = abs(np.fft.rfft(frames * np.hanning(400), n=512)) ** 2
    mel = np.linspace(2595*np.log10(1+80/700), 2595*np.log10(1+7600/700), 42)
    bins = np.floor((512+1)*(700*(10**(mel/2595)-1))/16000).astype(int)
    bank = np.zeros((40,257))
    for i in range(40):
        a,b,c = bins[i:i+3]
        for k in range(a,b): bank[i,k] = (k-a)/max(1,b-a)
        for k in range(b,c): bank[i,k] = (c-k)/max(1,c-b)
    basis = np.cos(np.pi / 40 * (np.arange(40)[:,None] + .5) * np.arange(1,14)[None,:]) * np.sqrt(2/40)
    cep = np.log(np.maximum(power @ bank.T, 1e-10)) @ basis
    cep -= cep.mean(axis=0)
    cep /= np.maximum(np.linalg.norm(cep, axis=1, keepdims=True), 1e-8)
    return cep[::2]


def distance(a,b):
    cost = 1 - a @ b.T
    prev = np.full(len(b)+1, np.inf);prev[0]=0
    for row in cost:
        cur=np.full(len(b)+1,np.inf)
        for j,v in enumerate(row): cur[j+1]=v+min(prev[j],prev[j+1],cur[j])
        prev=cur
    return float(prev[-1]/(len(a)+len(b)))


def main():
    p=argparse.ArgumentParser();p.add_argument("--data",type=Path,required=True);p.add_argument("--trace",type=Path,required=True);a=p.parse_args()
    transcripts={}
    for line in a.trace.read_text(encoding="utf-8").splitlines():
        r=json.loads(line)
        if r.get("stage")=="stt": transcripts[r["trace_id"]]=r.get("transcript","")
    clips={f.name:features(f) for f in a.data.glob("*.wav")}
    clips={k:v for k,v in clips.items() if v is not None}
    candidates=[k for k in clips if transcripts.get(k,"").strip(" .!?。") == "투투스"]
    result=[];started=time.perf_counter()
    for name, feat in clips.items():
        scores=[distance(feat,clips[t]) for t in candidates if t!=name]
        result.append(dict(file=name,stt_candidate=name in candidates,minimum_distance=min(scores) if scores else None))
    report=dict(status="OFFLINE_FEASIBILITY_ONLY_NOT_VALIDATED",clips=len(clips),candidate_templates=len(candidates),
                host_seconds=time.perf_counter()-started,results=result,
                warning="No threshold, accuracy or P4 latency inferred; human labels and held-out continuous audio required.")
    (a.data/"template_probe.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="results"}))


if __name__=="__main__": main()
