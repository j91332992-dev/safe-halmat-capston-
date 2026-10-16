"""Compare display transforms on identical raw evidence; no model input changes."""
import json,sys
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.config import settings
from app.services.camera_brightness import preview_image,brighten
cv2.setNumThreads(1)
source=Path(sys.argv[1]); image=cv2.imread(str(source))
assert image is not None
settings.camera_display_gamma=1.35;settings.camera_sharpen_amount=.2
inference_before=brighten(image)
rows=[]
for gamma,red,blue in ((1.35,1.,1.),(1.5,1.,1.),(1.65,1.08,.96)):
    settings.camera_preview_gamma=gamma;settings.camera_preview_red_gain=red;settings.camera_preview_blue_gain=blue
    output=preview_image(image)
    gray=cv2.cvtColor(output,cv2.COLOR_BGR2GRAY)
    name=source.parent/f'preview-{gamma}.jpg'
    cv2.imwrite(str(name),output,[cv2.IMWRITE_JPEG_QUALITY,95])
    rows.append(dict(gamma=gamma,red_gain=red,blue_gain=blue,mean_luma=float(gray.mean()),
        luma_p10_p50_p90=np.percentile(gray,[10,50,90]).tolist(),
        any_channel_clipped_fraction=float((output.max(axis=2)>=255).mean()),
        inference_pixels_unchanged=bool(np.array_equal(inference_before,brighten(image)))))
(source.parent/'brightness-comparison.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps(rows,indent=2))
