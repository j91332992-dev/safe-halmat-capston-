"""Flash only the verified tag's app0 after checking backup and build hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".pio-core/packages/tool-esptoolpy"))
import esptool
from esptool.targets.esp32 import ESP32ROM


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM6")
    parser.add_argument("--backup-manifest", type=Path, required=True)
    parser.add_argument("--build-manifest", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    args = parser.parse_args()
    backup = json.loads(args.backup_manifest.read_text(encoding="utf-8"))
    build = json.loads(args.build_manifest.read_text(encoding="utf-8"))
    if not backup.get("device_verified"):
        raise ValueError("Backup is not device-verified")
    original = Path(backup["backup_file"]).read_bytes()
    if len(original) != 16777216 or hashlib.sha256(original).hexdigest() != backup["sha256"]:
        raise ValueError("Backup file changed")
    data = args.image.read_bytes()
    if hashlib.sha256(data).hexdigest() != build["new_app_sha256"]:
        raise ValueError("Build image SHA-256 differs from manifest")
    app = next(partition for partition in backup["partitions"] if partition["label"] == "app0")
    if app["offset"] != 0x10000 or len(data) > app["size"] or data[0] != 0xE9:
        raise ValueError("Unexpected application partition/image")
    esp = ESP32ROM(args.port, 115200)
    try:
        esp.connect()
        mac = ":".join(f"{value:02x}" for value in esp.read_mac())
        if mac != backup["mac"] or mac != build["mac"]:
            raise ValueError("Connected tag differs from backup/build manifest")
        build["status"] = "flash_write_started"
        args.build_manifest.write_text(json.dumps(build, indent=2), encoding="utf-8")
        try:
            esptool.main(["--chip", "esp32", "--port", args.port, "--baud", "921600",
                          "--after", "hard_reset", "write_flash", "--flash_mode", "keep",
                          "--flash_freq", "keep", "--flash_size", "keep", "0x10000", str(args.image)], esp=esp)
        except Exception as error:
            build.update(status="flash_failed", error=str(error))
            args.build_manifest.write_text(json.dumps(build, indent=2), encoding="utf-8")
            raise
        build.update(status="flashed_hash_verified", backup_manifest=str(args.backup_manifest.resolve()))
        args.build_manifest.write_text(json.dumps(build, indent=2), encoding="utf-8")
        print("Application uploaded and device digest verified; bootloader/partition/NVS were not written.", flush=True)
    finally:
        esp._port.close()


if __name__ == "__main__":
    main()
