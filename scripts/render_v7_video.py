from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
timeline = json.loads((ROOT / "work/v7_video_timeline.json").read_text(encoding="utf-8"))
output = ROOT / "output/Crasheye_V7_female_exec_4k.mp4"
audio = ROOT / "work/voice/narration_v7_female_exec_48k_mono.wav"
subtitle = ROOT / "Crasheye_V9字幕_产品报告_v7_adjusted.ass"

command = ["ffmpeg", "-y"]
for segment in timeline["segments"]:
    command += ["-i", segment["source_absolute"]]
audio_index = len(timeline["segments"])
command += ["-i", str(audio)]

filters = []
for index, segment in enumerate(timeline["segments"]):
    span = max(float(segment["source_span"]), 1e-6)
    duration = float(segment["output_duration"])
    factor = duration / span
    filters.append(
        f'[{index}:v]trim=start={segment["source_start"]}:end={segment["source_end"]},'
        f'setpts=PTS-STARTPTS,setpts=PTS*{factor:.12f},fps=24,'
        f'tpad=stop_mode=clone:stop_duration=1,trim=duration={duration:.12f},'
        'setpts=PTS-STARTPTS,scale=3840:2160:force_original_aspect_ratio=decrease:'
        'flags=lanczos,pad=3840:2160:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,'
        f'format=yuv420p[v{index}]'
    )
joined = "".join(f"[v{i}]" for i in range(len(timeline["segments"])))
filters.append(f'{joined}concat=n={len(timeline["segments"])}:v=1:a=0,subtitles={subtitle.name!r}[vout]')
command += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", f"{audio_index}:a:0",
            "-af", "apad,atrim=duration=202", "-c:v", "h264_nvenc", "-preset", "p5",
            "-rc:v", "vbr", "-cq:v", "20", "-b:v", "0", "-r", "24", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
            str(output)]
(ROOT / "work/v7_ffmpeg_command.json").write_text(json.dumps(command, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"inputs": len(timeline["segments"]), "audio_index": audio_index, "output": str(output)}, ensure_ascii=False))
subprocess.run(command, cwd=ROOT, check=True)
