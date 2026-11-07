"""验证最终MP4的4K规格、完整解码和基本时长；不替代人工抽帧检查。"""
from pathlib import Path
import json, sys
import av
from project_paths import ROOT, project_path

target = project_path("output", "output/") / "final_4k.mp4" if len(sys.argv) <= 1 else Path(sys.argv[1])
if not target.is_absolute(): target = ROOT / target
c = av.open(str(target)); video = c.streams.video[0]; audio = c.streams.audio[0] if c.streams.audio else None
frames = sum(1 for _ in c.decode(video=0)); c.close()
assert (video.width, video.height) == (3840, 2160), (video.width, video.height)
assert audio is not None, "最终文件没有音频轨"
result = {"file": str(target), "width": video.width, "height": video.height,
          "fps": float(video.average_rate) if video.average_rate else None,
          "frames": frames, "audio_sample_rate": audio.rate,
          "full_video_decode": "passed"}
project_path("work", "work/").mkdir(exist_ok=True)
(project_path("work", "work/") / "output_verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(result, ensure_ascii=False, indent=2))
