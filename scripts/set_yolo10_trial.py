"""Apply only the camera trial settings; do not print or copy unrelated secrets."""
from pathlib import Path
import re
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--restore-quality',action='store_true')
args=parser.parse_args()
p=Path(__file__).resolve().parents[1]/'backend'/'.env'
text=p.read_text(encoding='utf-8-sig')
values={'YOLO_TARGET_FPS':'10','YOLO_IMAGE_SIZE':'320','YOLO_PPE_DETAIL_IMAGE_SIZE':'640',
        'YOLO_PPE_DETAIL_INTERVAL_SECONDS':'1.0','YOLO_PPE_DETAIL_960_ENABLED':'false','YOLO_TRACE_ENABLED':'true'}
if args.restore_quality:
    values.update(YOLO_IMAGE_SIZE='640',YOLO_PPE_DETAIL_INTERVAL_SECONDS='0.30',YOLO_PPE_DETAIL_960_ENABLED='true')
for key,value in values.items():
    pattern=rf'(?mi)^{key}\s*=.*$'
    if re.search(pattern,text): text=re.sub(pattern,lambda _:f'{key}={value}',text)
    else:text+='\n'+key+'='+value+'\n'
p.write_text(text,encoding='utf-8')
print('Camera trial settings applied:',values)
