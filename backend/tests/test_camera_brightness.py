import numpy as np
from app.services.camera_brightness import brighten, _lut
from app.config import settings

def test_disabled_is_identity(monkeypatch):
    monkeypatch.setattr(settings, 'camera_display_gamma', 1.0)
    monkeypatch.setattr(settings, 'camera_sharpen_amount', 0.0)
    image=np.array([0,64,128,255],dtype=np.uint8)
    assert brighten(image) is image

def test_lift_preserves_endpoints_and_monotonicity():
    lut=_lut(1.2)
    assert lut[0]==0 and lut[255]==255
    assert lut[128]>128
    assert np.all(np.diff(lut.astype(int))>=0)

def test_invalid_image_is_preserved():
    assert brighten(None) is None

def test_preview_override_does_not_change_inference(monkeypatch):
    monkeypatch.setattr(settings, 'camera_display_gamma', 1.35)
    monkeypatch.setattr(settings, 'camera_sharpen_amount', 0.0)
    image=np.full((8,8,3),64,dtype=np.uint8)
    before=brighten(image)
    preview=brighten(image,gamma=1.5)
    assert preview.mean()>before.mean()
    assert np.array_equal(before,brighten(image))

def test_color_preview_leaves_source_and_inference_unchanged(monkeypatch):
    from app.services.camera_brightness import preview_image
    monkeypatch.setattr(settings,'camera_preview_gamma',1.65)
    monkeypatch.setattr(settings,'camera_preview_red_gain',1.08)
    monkeypatch.setattr(settings,'camera_preview_blue_gain',.96)
    source=np.full((10,10,3),80,dtype=np.uint8)
    original=source.copy();expected=brighten(source).copy()
    displayed=preview_image(source)
    assert displayed[0,0,2]>displayed[0,0,0]
    assert np.array_equal(source,original)
    assert np.array_equal(brighten(source),expected)

def test_sharpen_keeps_uniform_highlights(monkeypatch):
    monkeypatch.setattr(settings, 'camera_display_gamma', 1.35)
    monkeypatch.setattr(settings, 'camera_sharpen_amount', .2)
    image=np.full((8,8,3),255,dtype=np.uint8)
    assert np.array_equal(brighten(image),image)
