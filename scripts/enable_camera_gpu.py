"""Enable the validated optional GPU backend without printing other settings."""
import re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
assert (root/'backend/best_openvino_model/best.xml').exists(), 'Export FP32 model first'
p=root/'backend/.env';text=p.read_text(encoding='utf-8-sig')
key='YOLO_FAST_OPENVINO_GPU';pattern=rf'(?mi)^{key}\s*=.*$'
text=re.sub(pattern,key+'=true',text) if re.search(pattern,text) else text+'\n'+key+'=true\n'
p.write_text(text,encoding='utf-8')
print('Enabled optional FP32 GPU fast lane; CPU fallback retained')
