from app.services.detail_model import HybridDetailModel

def test_only_640_uses_gpu():
    calls=[]
    cpu=lambda image,**kw:calls.append(('cpu',kw['imgsz'])) or 'cpu'
    gpu=lambda image,**kw:calls.append(('gpu',kw['imgsz'])) or 'gpu'
    model=HybridDetailModel(cpu,gpu)
    assert model(None,imgsz=640)=='gpu'
    assert model(None,imgsz=960)=='cpu'
    assert model(None,imgsz=480)=='cpu'
    assert calls==[('gpu',640),('cpu',960),('cpu',480)]

def test_gpu_failure_falls_back_and_stays_on_cpu():
    calls=[]
    def gpu(*args,**kwargs):calls.append('gpu');raise RuntimeError('test')
    model=HybridDetailModel(lambda *a,**k:'cpu',gpu)
    assert model(None,imgsz=640)=='cpu'
    assert model(None,imgsz=640)=='cpu'
    assert calls==['gpu']
    assert all(t['engine']=='cpu' for t in model.timings)


def test_optional_960_gpu_preserves_requested_size():
    calls=[]
    def gpu960(image, **kwargs):
        calls.append(kwargs['imgsz'])
        return 'gpu960'
    model=HybridDetailModel(lambda *a,**k:'cpu',lambda *a,**k:'gpu640',gpu960)
    assert model(None,imgsz=960)=='gpu960'
    assert model(None,imgsz=480)=='cpu'
    assert calls==[960]
