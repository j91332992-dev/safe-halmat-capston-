"""Verify one full-flash snapshot on a single esptool connection; no flash writes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".pio-core/packages/tool-esptoolpy"))
from esptool.targets.esp32 import ESP32ROM
from inspect_uwb_flash import inspect_flash


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM6")
    parser.add_argument("--mac", required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = bytearray(args.candidate.read_bytes())
    if len(data) != 16777216:
        raise ValueError("Candidate must be exactly 16 MiB")
    esp = ESP32ROM(args.port, 115200)
    try:
        esp.connect()
        mac = ":".join(f"{value:02x}" for value in esp.read_mac())
        if mac.lower() != args.mac.lower():
            raise ValueError("Connected tag MAC mismatch")
        esp = esp.run_stub()
        esp.change_baud(921600)
        esp.flash_set_parameters(len(data))
        # Previous whole dumps differed only in NVS. Refresh that state in the
        # same ROM/stub session and prove EVERY byte via the whole-flash digest.
        data[0x9000:0xE000] = esp.read_flash(0x9000, 0x5000)
        device_md5 = esp.flash_md5sum(0, len(data))
        if hashlib.md5(data).hexdigest() != device_md5:
            print("Other bytes differ; taking a fresh full dump on this connection.", flush=True)
            last_percent = -10
            def progress(done, total):
                nonlocal last_percent
                percent = int(done * 100 / total)
                if percent >= last_percent + 10:
                    print(f"Backup {percent}%", flush=True)
                    last_percent = percent
            data = esp.read_flash(0, len(data), progress)
            device_md5 = esp.flash_md5sum(0, len(data))
        if hashlib.md5(data).hexdigest() != device_md5:
            raise ValueError("Device digest differs from backup; do not flash")
        args.output.write_bytes(data)
        record = inspect_flash(args.output)
        record.update(device_verified=True, device_md5=device_md5, mac=mac,
                      method="whole-flash digest, single uninterrupted ROM/stub connection",
                      usb_serial="02E4F879")
        manifest = args.output.parent / "verified-backup-manifest.json"
        manifest.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps({"device_verified": True, "sha256": record["sha256"],
                          "bytes": len(data), "manifest": str(manifest)}, ensure_ascii=False), flush=True)
        esp.hard_reset()
    finally:
        esp._port.close()


if __name__ == "__main__":
    main()
