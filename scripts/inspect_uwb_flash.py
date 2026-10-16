"""Inspect a local ESP32 full-flash backup without dumping credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def inspect_flash(path: Path) -> dict:
    image = path.read_bytes()
    if len(image) != 16 * 1024 * 1024:
        raise ValueError("Expected the connected tag's complete 16 MiB backup")
    report = {"backup_file": str(path.resolve()), "size_bytes": len(image),
              "sha256": hashlib.sha256(image).hexdigest(), "partitions": []}
    for offset in range(0x8000, 0x9000, 32):
        entry = image[offset:offset+32]
        magic = struct.unpack_from("<H", entry)[0]
        if magic != 0x50AA:
            break
        _, kind, subtype, start, size, label, flags = struct.unpack("<HBBII16sI", entry)
        label = label.split(b"\0", 1)[0].decode("ascii", errors="replace")
        partition = {"type": kind, "subtype": subtype, "offset": start, "size": size,
                     "label": label, "flags": flags}
        if start + size > len(image):
            raise ValueError("Partition lies outside the backup")
        if kind == 0:
            partition["image_magic"] = image[start]
            descriptor = image[start+32:start+32+256]
            if struct.unpack_from("<I", descriptor)[0] == 0xABCD5432:
                def field(position, length):
                    return descriptor[position:position+length].split(b"\0", 1)[0].decode("ascii", errors="replace")
                partition["app_info"] = {"version": field(16, 32), "project_name": field(48, 32),
                                         "time": field(80, 16), "date": field(96, 16),
                                         "idf_version": field(112, 32),
                                         "elf_sha256": descriptor[144:176].hex()}
        elif kind == 1 and subtype == 0:
            partition["ota_sequences"] = [struct.unpack_from("<I", image, start+delta)[0]
                                           for delta in (0, 0x1000)]
        report["partitions"].append(partition)
    if not report["partitions"]:
        raise ValueError("No ESP32 partition table at expected 0x8000")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inspect_flash(args.backup)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
