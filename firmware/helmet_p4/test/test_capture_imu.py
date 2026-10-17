import importlib.util
import io
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("capture_p4_imu", ROOT / "scripts/capture_p4_imu.py")
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)


class CaptureTests(unittest.TestCase):
    def test_monitor_extract_preserves_reports_and_evidence(self):
        lines = [
            "I (20) hanmir_sensors: IMU1,20000,19000,1,255,3,0,0,9.80665,0,0\n",
            "I (21) hanmir_sensors: IMU1,21000,20000,20,0,0,-123,456,789,0,42\n",
            "W (22) hanmir_sensors: FALL_SUSPECTED id=1\n",
            "W (23) hanmir_sensors: IMU_LOG_DROPPED total=2\n",
            "I (24) hanmir_sensors: IMU1,broken\n",
        ]
        output, evidence = io.StringIO(), io.StringIO()
        self.assertEqual(CAPTURE.extract(lines, output, evidence), 2)
        self.assertEqual(len(output.getvalue().splitlines()), 3)
        self.assertIn("-123,456,789", output.getvalue())
        self.assertEqual(evidence.getvalue(), "".join(lines))


if __name__ == "__main__":
    unittest.main()
