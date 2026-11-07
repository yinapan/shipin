"""Generate narration with CosyVoice/CosyVoice2 zero-shot voice cloning."""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]


def _load_cosyvoice(model_dir: Path, device: str, source_dir: Path | None = None) -> Any:
    import torch
    if device != "cuda":
        raise ValueError("当前官方 CosyVoice 自动选择设备；此入口要求 --device cuda")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA 不可用，请先安装 CUDA 版 PyTorch 并检查显卡驱动")
    if not model_dir.is_dir():
        raise FileNotFoundError(f"模型目录不存在: {model_dir}")
    source_dir = source_dir or ROOT / "tools/CosyVoice"
    for path in (source_dir, source_dir / "third_party/Matcha-TTS"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    factory = importlib.import_module("cosyvoice.cli.cosyvoice").AutoModel
    return factory(model_dir=str(model_dir), load_trt=False, fp16=False)


def _array(speech: Any) -> np.ndarray:
    if hasattr(speech, "detach"):
        speech = speech.detach().float().cpu().numpy()
    value = np.asarray(speech, dtype=np.float32)
    if value.ndim == 2 and value.shape[0] == 1:
        value = value[0]
    if value.ndim != 1 or not value.size or not np.isfinite(value).all():
        raise ValueError("CosyVoice 输出必须是有限的非空单声道音频")
    return np.clip(value, -1.0, 1.0)


def generate(*, model_dir: Path, reference_audio: Path, prompt_text: str,
             text: str, output: Path, device: str, speed: float = 1.0,
             source_dir: Path | None = None, output_rate: int = 48000) -> Path:
    if not reference_audio.is_file():
        raise FileNotFoundError(f"参考音频不存在: {reference_audio}")
    if not text.strip() or not prompt_text.strip():
        raise ValueError("待合成文本和 --prompt-text 都不能为空")
    if output.exists():
        raise FileExistsError(f"输出已存在，请使用新文件名: {output}")
    if output_rate <= 0:
        raise ValueError("output_rate 必须大于零")
    if not np.isfinite(speed) or speed <= 0:
        raise ValueError("speed 必须是大于零的有限值")
    import torchaudio  # type: ignore

    cosyvoice = _load_cosyvoice(model_dir, device, source_dir)
    results = cosyvoice.inference_zero_shot(text, prompt_text, str(reference_audio), stream=False, speed=speed)
    chunks = []
    for result in results:
        chunks.append(_array(result["tts_speech"] if isinstance(result, dict) else result))
    if not chunks:
        raise RuntimeError("CosyVoice 没有返回语音片段")
    output.parent.mkdir(parents=True, exist_ok=True)
    samples = np.concatenate(chunks)
    if cosyvoice.sample_rate != output_rate:
        import torch
        samples = torchaudio.functional.resample(torch.from_numpy(samples), cosyvoice.sample_rate, output_rate).numpy()
    # Exclusive creation also protects against another process creating the output meanwhile.
    handle = output.open("xb")
    try:
        with handle:
            sf.write(handle, samples, output_rate, subtype="PCM_16", format="WAV")
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="使用 CosyVoice 生成项目旁白")
    parser.add_argument("--config", type=Path, default=ROOT / "project_config.json")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--reference-audio", type=Path)
    parser.add_argument("--prompt-text")
    parser.add_argument("--text")
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--speed", type=float, default=1.0)
    args = parser.parse_args()
    args.config = args.config.resolve()
    base = args.config.parent
    def resolve(value):
        path = Path(value)
        return path if path.is_absolute() else base / path
    with args.config.open(encoding="utf-8") as handle:
        config = json.load(handle)
    voice = config.get("voice", {})
    cosy = voice.get("cosyvoice", {})
    text = args.text or (resolve(args.text_file).read_text(encoding="utf-8") if args.text_file else "")
    output = resolve(args.output or cosy.get("output_file", "work/voice/cosyvoice.wav"))
    result = generate(
        model_dir=resolve(args.model_dir or cosy.get("model_dir", "tools/models/CosyVoice2-0.5B")),
        reference_audio=resolve(args.reference_audio or voice["reference_file"]),
        prompt_text=args.prompt_text or cosy.get("prompt_text", ""), text=text,
        output=output, device=args.device, speed=args.speed,
        source_dir=resolve(args.source_dir or cosy.get("source_dir", "tools/CosyVoice")),
        output_rate=int(config.get("delivery", {}).get("audio_sample_rate", 48000)),
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
