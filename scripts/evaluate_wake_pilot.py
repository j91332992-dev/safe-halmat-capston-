"""Clip-level pilot evaluation. Not continuous false-accept or device latency evidence."""
import argparse
import hashlib
import json
import wave
from pathlib import Path
import numpy as np
from ai_edge_litert.interpreter import Interpreter
from microwakeword.audio.audio_utils import generate_features_for_clip

p = argparse.ArgumentParser()
p.add_argument('--model', type=Path, required=True)
p.add_argument('--data', type=Path, required=True)
p.add_argument('--manifest', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--ignore-startup-outputs', type=int, default=0,
               help='Diagnostic exclusion of initial inference outputs; default evaluates every output.')
a = p.parse_args()
if a.ignore_startup_outputs < 0: p.error('startup exclusion must be nonnegative')
rows = []
for item in json.loads(a.manifest.read_text())['files']:
    source = a.data / item['file']
    if hashlib.sha256(source.read_bytes()).hexdigest() != item['sha256']:
        raise ValueError('Source changed since split creation')
    with wave.open(str(source), 'rb') as w:
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2')
    x = np.concatenate([np.zeros(8000, dtype=np.int16), pcm, np.zeros(1600, dtype=np.int16)])
    features = generate_features_for_clip(x, step_ms=10)
    # Fresh interpreter per clip: internal resource variables must not leak.
    i = Interpreter(model_path=str(a.model), num_threads=1)
    i.allocate_tensors()
    inp, out = i.get_input_details()[0], i.get_output_details()[0]
    scale, zero = inp['quantization']
    oscale, ozero = out['quantization']
    stride = int(inp['shape'][1])
    scores = []
    for end in range(stride, len(features)+1, stride):
        # Match upstream truncation, but saturate instead of wrapping int8.
        q = np.clip(features[end-stride:end]/scale+zero, -128, 127).astype(np.int8)
        i.set_tensor(inp['index'], q.reshape(inp['shape']))
        i.invoke()
        scores.append(float((int(i.get_tensor(out['index']).flat[0])-ozero)*oscale))
    rows.append({**item, 'duration_s': len(pcm)/16000, 'scores': scores,
                 'max_score': max(scores, default=0),
                 'decision_max_score': max(scores[a.ignore_startup_outputs:], default=0)})
tables = {}
for split in ('training', 'validation', 'testing'):
    subset = [r for r in rows if r['split'] == split]
    tables[split] = []
    for threshold in (.5, .7, .8, .9, .95):
        positive = [r for r in subset if r['label'] == 'positive']
        negative = [r for r in subset if r['label'] == 'negative']
        tables[split].append(dict(threshold=threshold, positive_clips=len(positive),
            detected=sum(r['decision_max_score'] >= threshold for r in positive),
            negative_clips=len(negative), false_positive_clips=sum(r['decision_max_score'] >= threshold for r in negative)))
report = dict(model_sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),
    limitation='Single speaker/session; no word-end labels, no continuous background, no P4 timing. Do not claim real-world accuracy or FA/hour.',
    ignore_startup_outputs=a.ignore_startup_outputs, thresholds=tables, clips=rows)
a.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(tables, indent=2))
