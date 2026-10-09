"""Compare bounded Korean command recordings on two OpenAI transcription models.

Manifest CSV columns: file,reference. Paths are relative to the manifest.
This script makes paid API calls only when explicitly run with OPENAI_API_KEY.
"""

import argparse
import csv
import os
from pathlib import Path
import re
from statistics import mean, median
from time import perf_counter
import wave

from openai import OpenAI


# Published estimated per-minute rates on 2026-10-02; billing may differ.
USD_PER_MINUTE = {
    "gpt-4o-mini-transcribe": 0.003,
    "gpt-transcribe": 0.0045,
}


def normalized(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", text).lower()


def edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for i, char in enumerate(left, 1):
        current = [i]
        for j, other in enumerate(right, 1):
            current.append(min(current[j - 1] + 1, previous[j] + 1,
                               previous[j - 1] + (char != other)))
        previous = current
    return previous[-1]


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--out", type=Path, default=Path("stt_comparison.csv"))
    parser.add_argument("--models", nargs="+", default=list(USD_PER_MINUTE))
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()
    if not os.environ.get("OPENAI_API_KEY"):
        parser.error("Set OPENAI_API_KEY in the shell before running the benchmark")

    with args.manifest.open("r", encoding="utf-8-sig", newline="") as source:
        samples = list(csv.DictReader(source))
    if not samples or any(not row.get("file") or not row.get("reference") for row in samples):
        parser.error("Manifest must contain nonempty file and reference columns")

    client = OpenAI(timeout=args.timeout, max_retries=0)
    rows: list[dict] = []
    for index, sample in enumerate(samples):
        path = args.manifest.parent / sample["file"]
        duration = wav_seconds(path)
        # Alternate order to reduce the effect of time-dependent network load.
        models = args.models if index % 2 == 0 else list(reversed(args.models))
        for model in models:
            start = perf_counter()
            try:
                with path.open("rb") as audio:
                    request = dict(
                        model=model,
                        file=audio,
                        prompt="한국어 산업 안전 현장 대화입니다. 작업자의 명령을 정확히 받아쓰세요.",
                    )
                    if model == "gpt-transcribe":
                        request["extra_body"] = {"languages": ["ko"]}
                    else:
                        request["language"] = "ko"
                    result = client.audio.transcriptions.create(**request)
                transcript = (result if isinstance(result, str) else result.text).strip()
                error = ""
            except Exception as exc:
                transcript, error = "", type(exc).__name__
            latency_ms = round((perf_counter() - start) * 1000, 1)
            reference = normalized(sample["reference"])
            hypothesis = normalized(transcript)
            rows.append({
                "file": sample["file"], "model": model,
                "reference": sample["reference"], "transcript": transcript,
                "duration_s": round(duration, 2), "latency_ms": latency_ms,
                "cer": round(edit_distance(reference, hypothesis) / max(len(reference), 1), 3)
                if not error else "",
                "estimated_usd": round(duration / 60 * USD_PER_MINUTE.get(model, 0), 7),
                "error": error,
            })
            print(f"{sample['file']} {model}: {latency_ms} ms, CER={rows[-1]['cer']} {error}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for model in args.models:
        valid = [row for row in rows if row["model"] == model and not row["error"]]
        if valid:
            latencies = sorted(row["latency_ms"] for row in valid)
            p95 = latencies[max(0, int(0.95 * len(latencies) + 0.999999) - 1)]
            print(f"{model}: n={len(valid)} mean CER={mean(row['cer'] for row in valid):.3f}, "
                  f"median={median(latencies):.1f} ms, p95={p95:.1f} ms, "
                  f"estimated cost=${sum(row['estimated_usd'] for row in valid):.5f}")
    print(f"saved {args.out}")


if __name__ == "__main__":
    main()
