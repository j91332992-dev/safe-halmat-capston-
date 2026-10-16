"""Inspect an exported model before attempting a P4 interpreter integration."""
import argparse
import hashlib
import json
from pathlib import Path
from ai_edge_litert.interpreter import Interpreter

p=argparse.ArgumentParser();p.add_argument('model',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
i=Interpreter(model_path=str(a.model));i.allocate_tensors()
def info(t):
    return dict(name=t['name'],shape=t['shape'].tolist(),dtype=str(t['dtype']),quantization=list(t['quantization']))
r=dict(sha256=hashlib.sha256(a.model.read_bytes()).hexdigest(),bytes=a.model.stat().st_size,
       inputs=[info(t) for t in i.get_input_details()],outputs=[info(t) for t in i.get_output_details()],
       operators=sorted(set(t['op_name'] for t in i._get_ops_details() if t['op_name'] != 'DELEGATE')),
       p4_validation='NOT_RUN',arena_bytes=None,threshold=None,
       warning='Desktop allocation does not prove TFLite Micro operator support or P4 timing. All streaming state tensors must be managed.')
a.output.write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r,indent=2))
