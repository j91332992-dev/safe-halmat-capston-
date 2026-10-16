"""Execute the exact firmware calculation, without a DW3000 or ESP32."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("program, expected", [
    ("test_ipatov", "Ipatov calculation checks passed"),
    ("test_delivery", "Delivery policy checks passed"),
])
def test_native_firmware(tmp_path, program, expected):
    if importlib.util.find_spec("ziglang") is None:
        pytest.skip("Optional host compiler: pip install ziglang")
    root = Path(__file__).resolve().parents[2]
    source = root / f"firmware/uwb_multi_test/test/{program}.cpp"
    executable = tmp_path / f"{program}.exe"
    subprocess.run([sys.executable, "-m", "ziglang", "c++", "-std=c++11", "-nostdlib++", str(source),
                    "-o", str(executable)], check=True, timeout=240)
    result = subprocess.run([str(executable)], check=True, capture_output=True, text=True, timeout=10)
    assert expected in result.stdout
