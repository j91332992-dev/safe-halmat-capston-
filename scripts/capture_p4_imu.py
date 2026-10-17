"""Extract IMU1 reports from a saved monitor log, stdin, or an optional serial port."""
import argparse
import csv
import json
from pathlib import Path
import re
import sys


FIELDS = ["received_us", "sensor_us", "sensor_id", "sequence", "status",
          "x", "y", "z", "w_or_temperature", "raw_us"]
REPORT = re.compile(r"IMU1,([0-9eE+.,-]+)")


def extract(lines, output, evidence):
    writer = csv.writer(output)
    writer.writerow(FIELDS)
    count = 0
    for line in lines:
        if isinstance(line, bytes):
            line = line.decode("utf-8", errors="replace")
        evidence.write(line if line.endswith("\n") else line + "\n")
        match = REPORT.search(line)
        if not match:
            continue
        values = match.group(1).split(",")
        if len(values) != len(FIELDS):
            continue
        try:
            for index in (0, 1, 2, 3, 4, 9):
                int(values[index])
            for index in (5, 6, 7, 8):
                float(values[index])
        except ValueError:
            continue
        writer.writerow(values)
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--input", type=Path, help="Existing UART/USB monitor text log; default stdin")
    source.add_argument("--port", help="Optional COM port (requires pyserial); does not intentionally reset device")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--label", required=True, help="Activity label, e.g. walking or helmet_drop")
    parser.add_argument("--mount", required=True, help="Sensor attachment location and axis directions")
    args = parser.parse_args()
    metadata = args.output.with_suffix(".metadata.json")
    evidence_path = args.output.with_suffix(".monitor.log")
    for path in (args.output, metadata, evidence_path):
        if path.exists():
            parser.error(f"Refusing to overwrite {path}")
    metadata.write_text(json.dumps({
        "schema": 1, "label": args.label, "mount": args.mount,
        "source": str(args.input) if args.input else args.port or "stdin",
        "baseline_commit": "9519ce6", "firmware_identity": "record actual running image separately",
        "units": {"1": "m/s2 including gravity", "2": "rad/s", "5": "quaternion xyzw",
                  "20": "ADC counts", "21": "ADC counts; fourth value is temperature counts"},
        "time": "sensor_us=SH2 reconstructed time; received_us=P4 monotonic callback time; raw_us=raw report clock",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    connection = None
    stream = sys.stdin
    try:
        if args.port:
            import serial
            connection = serial.Serial()
            connection.port = args.port
            connection.baudrate = args.baud
            connection.dtr = False
            connection.rts = False
            connection.timeout = 1
            connection.open()
            stream = iter(connection.readline, None)
        elif args.input:
            stream = args.input.open(encoding="utf-8", errors="replace")
        with args.output.open("x", newline="", encoding="utf-8") as output, evidence_path.open("x", encoding="utf-8") as evidence:
            extract(stream, output, evidence)
    except KeyboardInterrupt:
        pass
    finally:
        if connection:
            connection.close()
        elif stream is not sys.stdin:
            stream.close()


if __name__ == "__main__":
    main()
