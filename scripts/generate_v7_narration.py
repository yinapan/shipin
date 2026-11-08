"""Generate and time-fit all V7 narration segments with one CosyVoice model."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

from generate_voice_cosyvoice import _array, _load_cosyvoice


def ffmpeg_tempo_chain(ratio: float) -> str:
    factors = []
    while ratio > 2.0:
        factors.append(2.0)
        ratio /= 2.0
    while ratio < 0.5:
        factors.append(0.5)
        ratio /= 0.5
    factors.append(ratio)
    return ",".join(f"atempo={factor:.8f}" for factor in factors)


def trim_and_fit(raw: Path, output: Path, target: float, rate: int) -> dict:
    audio, raw_rate = sf.read(raw)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if raw_rate != rate:
        raise ValueError(f"unexpected raw sample rate {raw_rate}, expected {rate}")
    active = np.flatnonzero(np.abs(audio) >= 10 ** (-50 / 20))
    if not len(active):
        raise ValueError("raw output is silent")
    trimmed = audio[active[0] : active[-1] + 1]
    trimmed_path = raw.with_name(raw.stem + "_trim.wav")
    sf.write(trimmed_path, trimmed, rate, subtype="PCM_16")
    trimmed_seconds = len(trimmed) / rate
    ratio = trimmed_seconds / target
    filter_chain = ffmpeg_tempo_chain(ratio)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(trimmed_path),
         "-af", filter_chain, "-ar", str(rate), "-ac", "1", str(output)],
        check=True,
    )
    fitted, fitted_rate = sf.read(output)
    target_samples = round(target * rate)
    if len(fitted) > target_samples:
        fitted = fitted[:target_samples]
    elif len(fitted) < target_samples:
        fitted = np.pad(fitted, (0, target_samples - len(fitted)))
    # A short fade at each segment boundary prevents clicks when concatenated.
    fade = min(round(rate * 0.005), len(fitted) // 2)
    if fade:
        fitted[:fade] *= np.linspace(0.0, 1.0, fade, endpoint=False)
        fitted[-fade:] *= np.linspace(1.0, 0.0, fade, endpoint=False)
    sf.write(output, fitted, rate, subtype="PCM_16")
    return {
        "raw_seconds": len(audio) / rate,
        "trimmed_seconds": trimmed_seconds,
        "target_seconds": target,
        "tempo_ratio": ratio,
        "final_seconds": len(fitted) / fitted_rate,
        "final_samples": len(fitted),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=Path("work/v7_narration_manifest.json"))
    parser.add_argument("--reference-audio", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, default=Path("tools/models/CosyVoice2-0.5B"))
    parser.add_argument("--source-dir", type=Path, default=Path("tools/CosyVoice"))
    parser.add_argument("--output", type=Path, default=Path("work/voice/narration_v7_female_exec_48k_mono.wav"))
    parser.add_argument("--segments-dir", type=Path)
    parser.add_argument("--speed", type=float, default=2.5)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    segments_dir = args.segments_dir or (args.output.parent / "narration_v7_female_exec_segments")
    segments_dir.mkdir(parents=True, exist_ok=True)
    rate = 48000
    prompt_text = manifest["segments"][0]["tts_text"]
    model = _load_cosyvoice(args.model_dir, "cuda", args.source_dir)
    records = []
    fitted_audio = []
    for number, segment in enumerate(manifest["segments"], 1):
        segment_id = segment["id"]
        print(f"[{number}/{len(manifest['segments'])}] {segment_id}", flush=True)
        raw_path = segments_dir / f"{segment_id}_raw_{model.sample_rate // 1000}k.wav"
        raw_48k_path = segments_dir / f"{segment_id}_raw_48k.wav"
        fitted_path = segments_dir / f"{segment_id}_48k.wav"
        results = model.inference_zero_shot(
            segment["tts_text"], prompt_text, str(args.reference_audio),
            stream=False, speed=args.speed,
        )
        chunks = [_array(item["tts_speech"] if isinstance(item, dict) else item) for item in results]
        if not chunks:
            raise RuntimeError(f"no speech returned for {segment_id}")
        raw = np.concatenate(chunks)
        sf.write(raw_path, raw, model.sample_rate, subtype="PCM_16")
        # The model emits 24 kHz; resample to the delivery rate before timing.
        resampled = np.interp(
            np.linspace(0, len(raw), round(len(raw) * rate / model.sample_rate), endpoint=False),
            np.arange(len(raw)), raw,
        ).astype(np.float32)
        sf.write(raw_48k_path, resampled, rate, subtype="PCM_16")
        target = float(segment["duration"])
        timing = trim_and_fit(raw_48k_path, fitted_path, target, rate)
        fitted, fitted_rate = sf.read(fitted_path)
        fitted_audio.append(fitted.astype(np.float32))
        records.append({"id": segment_id, "text_nonempty": bool(segment["tts_text"].strip()), **timing,
                        "sample_rate": fitted_rate, "channels": 1 if fitted.ndim == 1 else fitted.shape[1],
                        "raw_path": str(raw_path), "raw_48k_path": str(raw_48k_path),
                        "fitted_path": str(fitted_path)})
    final = np.concatenate(fitted_audio)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.output, final, rate, subtype="PCM_16")
    report = {"segments": records, "segment_count": len(records), "total_seconds": len(final) / rate,
              "sample_rate": rate, "channels": 1, "text_nonempty": all(r["text_nonempty"] for r in records)}
    report_path = args.output.with_suffix(".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "report": str(report_path),
                      "segments": len(records), "total_seconds": len(final) / rate}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
