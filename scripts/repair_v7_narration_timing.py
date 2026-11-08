from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import soundfile as sf

from generate_voice_cosyvoice import _array, _load_cosyvoice
from generate_v7_narration import trim_and_fit

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "work/voice/narration_v7_female_exec_48k_mono.report.json"
MANIFEST_PATH = ROOT / "work/v7_narration_manifest.json"
REF = ROOT / "wav/MiniMax_2026-11-08_10_20_38_新闻女声_no-watermark.wav"
MODEL_DIR = ROOT / "tools/models/CosyVoice2-0.5B"
SOURCE_DIR = ROOT / "tools/CosyVoice"
SEG_DIR = ROOT / "work/voice/narration_v7_female_exec_segments"
FINAL = ROOT / "work/voice/narration_v7_female_exec_48k_mono.wav"

report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
segments = {item["id"]: item for item in manifest["segments"]}
model = _load_cosyvoice(MODEL_DIR, "cuda", SOURCE_DIR)
prompt_text = manifest["segments"][0]["tts_text"]
repaired = []
for record in report["segments"]:
    record.setdefault("speed", 2.5)
    if record["tempo_ratio"] >= 0.75:
        continue
    segment_id = record["id"]
    item = segments[segment_id]
    old_fitted = Path(record["fitted_path"])
    initial = old_fitted.with_name(old_fitted.stem + "_initial.wav")
    if old_fitted.exists() and not initial.exists():
        shutil.copy2(old_fitted, initial)
    speed = max(0.5, min(2.5, 2.5 * record["tempo_ratio"]))
    print(f"repair {segment_id} speed={speed:.3f}", flush=True)
    results = model.inference_zero_shot(
        item["tts_text"], prompt_text, str(REF), stream=False, speed=speed
    )
    raw = np.concatenate([_array(x["tts_speech"] if isinstance(x, dict) else x) for x in results])
    raw24 = SEG_DIR / f"{segment_id}_repair_raw_24k.wav"
    raw48 = SEG_DIR / f"{segment_id}_repair_raw_48k.wav"
    sf.write(raw24, raw, model.sample_rate, subtype="PCM_16")
    resampled = np.interp(
        np.linspace(0, len(raw), round(len(raw) * 48000 / model.sample_rate), endpoint=False),
        np.arange(len(raw)), raw,
    ).astype(np.float32)
    sf.write(raw48, resampled, 48000, subtype="PCM_16")
    timing = trim_and_fit(raw48, old_fitted, float(item["duration"]), 48000)
    record.update(timing, speed=speed, repaired=True, initial_fitted_path=str(initial))
    repaired.append(segment_id)

fitted_audio = []
for item in manifest["segments"]:
    path = Path(report["segments"][[x["id"] for x in report["segments"]].index(item["id"])] ["fitted_path"])
    audio, rate = sf.read(path)
    if rate != 48000 or audio.ndim != 1:
        raise ValueError(f"invalid fitted segment {item['id']}")
    fitted_audio.append(audio.astype(np.float32))
final = np.concatenate(fitted_audio)
sf.write(FINAL, final, 48000, subtype="PCM_16")
report["repaired_segments"] = repaired
report["total_seconds"] = len(final) / 48000
REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"repaired": len(repaired), "segments": len(report["segments"]), "total_seconds": len(final) / 48000}, ensure_ascii=False))
