"""扫描项目中的视频、音频和剧本，生成 work/asset_inventory.json。

运行：python scripts/scan_assets.py
素材放在项目根目录的 mp4/ 和 wav/，脚本不会修改素材。
"""
from pathlib import Path
import hashlib, json, re
import av
from project_paths import ROOT, project_path

VIDEOS = project_path("videos", "mp4/")
AUDIO = project_path("audio", "wav/")
WORK = project_path("work", "work/")
WORK.mkdir(exist_ok=True)

def natural_episode_shot(p: Path):
    rel = p.relative_to(VIDEOS)
    folder = "/".join(rel.parts[:-1])
    m_ep = re.search(r"第\s*(\d+)\s*集", folder)
    m_shot = re.search(r"shot\s*0*(\d+)", p.stem, re.I)
    if not m_ep or not m_shot:
        raise ValueError(f"无法从路径解析集数或shot编号：{rel}")
    return int(m_ep.group(1)), int(m_shot.group(1)), p.name

def video_info(p: Path):
    c = av.open(str(p)); stream = c.streams.video[0]
    info = {
        "path": str(p.relative_to(ROOT)),
        "episode": natural_episode_shot(p)[0],
        "shot": natural_episode_shot(p)[1],
        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "duration": float(c.duration / av.time_base) if c.duration else None,
        "width": stream.width, "height": stream.height,
        "fps": float(stream.average_rate) if stream.average_rate else None,
        "has_audio": bool(c.streams.audio),
    }
    c.close(); return info

videos = [video_info(p) for p in VIDEOS.rglob("*.mp4")]
videos.sort(key=lambda x: (x["episode"], x["shot"], x["path"]))
audios = []
for p in sorted(AUDIO.rglob("*.wav")):
    c = av.open(str(p)); stream = c.streams.audio[0] if c.streams.audio else None
    audios.append({"path": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                   "duration": float(c.duration / av.time_base) if c.duration else None,
                   "sample_rate": stream.rate if stream else None, "channels": stream.channels if stream else None})
    c.close()
scripts = [str(p.relative_to(ROOT)) for p in sorted(ROOT.rglob("*.md")) if "分享包" not in str(p)]
out = {"video_count": len(videos), "audio_count": len(audios), "videos": videos, "audios": audios, "script_files": scripts,
       "ordering_rule": "episode number first, then shot number within each episode"}
(WORK / "asset_inventory.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"video_count": len(videos), "audio_count": len(audios), "ordered_videos": videos}, ensure_ascii=False, indent=2))
