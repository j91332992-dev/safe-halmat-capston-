"""Save PCM: lines from the P4 AFE console as a 16 kHz mono WAV file."""

import argparse
import base64
from pathlib import Path
from time import monotonic
import wave

import serial


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="For example COM12")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--baud", type=int, default=921600)
    parser.add_argument("--idle-timeout", type=float, default=10.0,
                        help="Stop if no PCM arrives for this many seconds")
    args = parser.parse_args()

    target_bytes = int(args.seconds * 16000) * 2
    chunks: list[bytes] = []
    total = 0
    if args.seconds <= 0 or args.idle_timeout <= 0:
        parser.error("--seconds and --idle-timeout must be positive")
    last_pcm = monotonic()
    with serial.Serial(args.port, args.baud, timeout=1) as device:
        while total < target_bytes:
            line = device.readline().strip()
            if not line.startswith(b"PCM:"):
                if monotonic() - last_pcm >= args.idle_timeout:
                    raise TimeoutError("No PCM data received; check the port and enable PCM output in menuconfig")
                continue
            try:
                chunk = base64.b64decode(line[4:], validate=True)
            except ValueError:
                continue
            last_pcm = monotonic()
            chunks.append(chunk)
            total += len(chunk)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(args.out), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"".join(chunks)[:target_bytes])
    print(f"saved {args.out} ({min(total, target_bytes) / 32000:.2f} s)")


if __name__ == "__main__":
    main()
