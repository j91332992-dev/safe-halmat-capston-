"""Use optional FP32 GPU models at their native sizes, with CPU fallback."""
import logging
import time

class HybridDetailModel:
    _hanmir_engine = 'hybrid_detail_fp32'

    def __init__(self, cpu, gpu, gpu960=None):
        self.cpu, self.gpu = cpu, gpu
        self.gpu960 = gpu960
        self.gpu_failed = False
        self.timings = []

    def __call__(self, image, **kwargs):
        size=kwargs.get('imgsz',640)
        gpu_model = self.gpu if size == 640 else self.gpu960 if size == 960 else None
        use_gpu = gpu_model is not None and not self.gpu_failed
        started=time.perf_counter()
        try:
            result=(gpu_model if use_gpu else self.cpu)(image,**kwargs)
        except Exception:
            if not use_gpu:raise
            logging.getLogger(__name__).exception('Detail GPU failed; preserving CPU fallback')
            self.gpu_failed=True;use_gpu=False
            result=self.cpu(image,**kwargs)
        self.timings.append({'size':size,'engine':'gpu' if use_gpu else 'cpu','ms':round((time.perf_counter()-started)*1000,2)})
        return result
