"""Check lab fault injection itself; this is not an ESP32/hardware test."""
import importlib.util
from pathlib import Path
import threading
import time
import urllib.request
import urllib.error

import pytest

spec = importlib.util.spec_from_file_location(
    "uwb_http_fault_server", Path(__file__).resolve().parents[2] / "scripts/uwb_http_fault_server.py")
fault = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fault)


@pytest.mark.parametrize("status, delay, disconnect", [(200, 0, False), (503, 0, False),
                                                     (200, 0.3, False), (200, 0, True)])
def test_lab_fault_endpoint(status, delay, disconnect, tmp_path):
    server = fault.make_server("127.0.0.1", 0, status=status, delay=delay,
                               disconnect=disconnect, log_path=tmp_path / "received.jsonl")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/api/uwb/distances",
                                     data=b'{"measurement_id":"boot:255"}', method="POST")
    # GetTickCount-based monotonic clocks can quantize by ~16 ms on Windows.
    # QueryPerformanceCounter measures the short injected delay accurately.
    started = time.perf_counter()
    try:
        if disconnect:
            import http.client
            with pytest.raises((OSError, http.client.RemoteDisconnected)):
                urllib.request.urlopen(request, timeout=2)
        elif status >= 400:
            with pytest.raises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(request, timeout=2)
            assert exc.value.code == status
        else:
            with urllib.request.urlopen(request, timeout=2) as response:
                assert response.status == status
        assert time.perf_counter() - started >= delay
        assert 'boot:255' in (tmp_path / "received.jsonl").read_text(encoding="utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)
