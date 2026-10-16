"""Export the same PPE weights at 960 FP32, without overwriting an existing run."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from ultralytics import YOLO

p = argparse.ArgumentParser()
p.add_argument('--weights', type=Path, default=Path(__file__).resolve().parents[1] / 'backend/best.pt')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
if a.output.exists():
    p.error('Choose a new output directory')
a.output.mkdir(parents=True)
weights = a.output / 'best.pt'
shutil.copyfile(a.weights, weights)
result = YOLO(str(weights)).export(format='openvino', imgsz=960, half=False, dynamic=False)
(a.output / 'export_manifest.json').write_text(json.dumps({
    'source_sha256': hashlib.sha256(weights.read_bytes()).hexdigest(),
    'imgsz': 960, 'precision': 'FP32', 'model_path': str(result),
}, indent=2), encoding='utf-8')
print('Set YOLO_DETAIL_GPU960_MODEL_PATH to:', result)
