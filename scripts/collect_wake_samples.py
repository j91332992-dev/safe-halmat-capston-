"""Preserve new helmet WAVs for manual labeling; never infer labels from STT."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import time
import wave
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=Path("backend/audio_data"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--speaker", default="speaker-001")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 600:
        parser.error("seconds must be between 1 and 600")
    args.output.mkdir(parents=True, exist_ok=True)
    seen = {p.name for p in args.source.glob("helmet-*.wav")}
    started = time.monotonic()
    count = 0
    with (args.output / "manifest.jsonl").open("a", encoding="utf-8") as manifest:
        while time.monotonic() - started < args.seconds and count < 200:
            for path in args.source.glob("helmet-*.wav"):
                if path.name in seen:
                    continue
                try:
                    if time.time() - path.stat().st_mtime < .2:
                        continue
                    data = path.read_bytes()
                    with wave.open(io.BytesIO(data), "rb") as wav:
                        if (wav.getframerate(), wav.getsampwidth(), wav.getnchannels()) != (16000, 2, 1):
                            seen.add(path.name)
                            continue
                        frames = wav.getnframes()
                        pcm = wav.readframes(frames)
                        if len(pcm) != frames * 2:
                            continue
                    (args.output / path.name).write_bytes(data)
                    row = dict(file=path.name, sha256=hashlib.sha256(data).hexdigest(),
                               seconds=frames / 16000, speaker=args.speaker,
                               captured_at=datetime.now(timezone.utc).isoformat(),
                               label="unreviewed", keyword_end_ms=None,
                               source="helmet_vad_post_afe", split="unassigned")
                    manifest.write(json.dumps(row) + "\n")
                    manifest.flush()
                    seen.add(path.name)
                    count += 1
                except (OSError, EOFError, wave.Error):
                    continue
            time.sleep(.1)
    print(json.dumps(dict(saved=count, output=str(args.output))))


if __name__ == "__main__":
    main()
