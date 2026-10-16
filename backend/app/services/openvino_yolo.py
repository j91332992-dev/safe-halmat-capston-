"""Optional FP32 CPU backend using the same Ultralytics detection postprocessing."""
def load_openvino_yolo(path, threads=3, device='CPU'):
    from pathlib import Path
    import openvino as ov
    import torch
    from ultralytics import YOLO
    model=YOLO(str(path),task='detect')
    # Bootstrap metadata on CPU; the callback compiles the actual requested
    # device once with explicit FP32 properties before any real prediction.
    model.overrides.update(device='intel:cpu',quantize=32)
    def configure(predictor):
        backend=predictor.model.backend
        if not getattr(backend,'_hanmir_fp32_ready',False):
            core=ov.Core();xml=next(Path(path).glob('*.xml'))
            graph=core.read_model(str(xml))
            cache=Path(path)/'.cache';cache.mkdir(exist_ok=True)
            options={'PERFORMANCE_HINT':'LATENCY','INFERENCE_PRECISION_HINT':ov.Type.f32,'CACHE_DIR':str(cache)}
            if device=='CPU':options.update(INFERENCE_NUM_THREADS=threads,NUM_STREAMS=1)
            backend.ov_compiled_model=core.compile_model(graph,device,options)
            backend._hanmir_fp32_ready=True
        torch.set_num_threads(threads)
    model.add_callback('on_predict_start',configure)
    model._hanmir_engine='openvino_'+device.lower()+'_fp32'
    return model
