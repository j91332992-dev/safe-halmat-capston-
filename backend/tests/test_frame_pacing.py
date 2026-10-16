from app.services.frame_pacing import next_deadline, inference_interval

def test_keeps_period_after_small_overrun():
    assert next_deadline(1.,1.03,.1)==1.1

def test_large_overrun_does_not_build_catchup_backlog():
    assert next_deadline(1.,5.,.1)==5.

def test_no_rate_change_without_overrun():
    assert next_deadline(1.,1.,.1)==1.1

def test_gpu_voice_keeps_target():
    assert inference_interval(.1,True,True,10)==.1

def test_cpu_voice_does_not_force_one_fps():
    assert inference_interval(.1,True,False,10)==.1

def test_voice_never_exceeds_configured_normal_target():
    assert inference_interval(.2,True,True,10)==.2
