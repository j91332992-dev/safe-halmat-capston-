import csv
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get("HANMIR_IMU_REPLAY_EXE"), "Set HANMIR_IMU_REPLAY_EXE to the compiled C replay executable")
class ReplayTests(unittest.TestCase):
    def replay(self, falling):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "imu.csv"
            with source.open("w", newline="", encoding="utf-8") as output:
                writer = csv.writer(output)
                writer.writerow(["received_us", "sensor_us", "sensor_id", "sequence", "status",
                                 "x", "y", "z", "w_or_temperature", "raw_us"])
                sequence = {1: 0, 2: 0, 5: 0}
                for index in range(300):
                    timestamp = (index + 1) * 20000
                    tilt = 70 if falling and index >= 100 else 0
                    angle = math.radians(tilt) / 2
                    reports = [(2, [3 if index == 100 else 0, 0, 0, 0])]
                    if index % 5 == 0:
                        reports.append((5, [math.sin(angle), 0, 0, math.cos(angle)]))
                    reports.append((1, [0, 0, (3 if index == 100 else 1) * 9.80665, 0]))
                    for sensor_id, values in reports:
                        writer.writerow([timestamp, timestamp, sensor_id, sequence[sensor_id], 3, *values, 0])
                        sequence[sensor_id] = (sequence[sensor_id] + 1) % 256
            result = subprocess.run([os.environ["HANMIR_IMU_REPLAY_EXE"], str(source)],
                                    check=True, capture_output=True, text=True, timeout=10)
            return result.stdout

    def test_impact_without_posture_change_does_not_trigger(self):
        self.assertEqual(self.replay(False), "")

    def test_50hz_with_10hz_orientation_triggers_once(self):
        self.assertEqual(self.replay(True).count("FALL_SUSPECTED"), 1)


if __name__ == "__main__":
    unittest.main()
