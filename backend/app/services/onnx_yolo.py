"""FP32 ONNX path with bounded CPU threads; keeps Ultralytics pre/postprocessing."""
def load_onnx_yolo(path, threads=2):
    import onnxruntime as ort
    from ultralytics import YOLO
    from ultralytics.models.yolo.detect import DetectionPredictor
    model=YOLO(str(path),task='detect')
    predictor=DetectionPredictor(overrides={'model':str(path),'task':'detect','device':'cpu','verbose':False})
    predictor.setup_model(str(path),verbose=False)
    backend=predictor.model.backend
    options=ort.SessionOptions()
    options.intra_op_num_threads=threads
    options.inter_op_num_threads=1
    options.add_session_config_entry('session.intra_op.allow_spinning','0')
    options.add_session_config_entry('session.inter_op.allow_spinning','0')
    backend.session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
    model.predictor=predictor
    return model
