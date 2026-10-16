"""Conservative midtone lift shared by preview and inference (not sensor exposure)."""
from functools import lru_cache
import cv2
import numpy as np
from ..config import settings

@lru_cache(maxsize=8)
def _lut(gamma):
    return np.rint(255 * (np.arange(256) / 255.0) ** (1.0 / gamma)).astype(np.uint8)

def brighten(image, *, gamma=None):
    if image is None:
        return image
    gamma = settings.camera_display_gamma if gamma is None else gamma
    result = image if gamma == 1.0 else cv2.LUT(image, _lut(float(gamma)))
    amount = float(settings.camera_sharpen_amount)
    if amount:
        blurred = cv2.GaussianBlur(result, (3, 3), 0.8)
        result = cv2.addWeighted(result, 1.0 + amount, blurred, -amount, 0)
    return result

def preview_image(image):
    """Display-only exposure/color adjustment; never used as model input."""
    gamma=settings.camera_preview_gamma or settings.camera_display_gamma
    result=brighten(image,gamma=gamma)
    if result is None:return result
    gains=(settings.camera_preview_blue_gain,1.0,settings.camera_preview_red_gain)
    if gains!=(1.0,1.0,1.0):
        # Mild global white balance, independent of detected objects/classes.
        lut=np.clip(np.arange(256)[:,None,None]*np.array(gains)[None,None,:],0,255).astype(np.uint8)
        result=cv2.LUT(result,lut)
    return result

def preview_jpeg(jpeg):
    gamma = settings.camera_preview_gamma or settings.camera_display_gamma
    if gamma == 1.0 and settings.camera_sharpen_amount == 0 and settings.camera_preview_red_gain == 1 and settings.camera_preview_blue_gain == 1:
        return jpeg
    image = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return jpeg
    ok, encoded = cv2.imencode('.jpg', preview_image(image), [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes() if ok else jpeg
