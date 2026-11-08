from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "V7时间轴与单行字幕说明.json").read_text(encoding="utf-8"))
inventory = json.loads((ROOT / "work/asset_inventory.json").read_text(encoding="utf-8"))
by_hash = {item["sha256"]: item for item in inventory["videos"]}
by_episode_shot = {(item["episode"], item["shot"]): item for item in inventory["videos"]}

segments = []
warnings = []
used = set()
for item in config["timeline"]:
    actual = by_hash.get(item["sha256"])
    mapping = "sha256"
    if actual is None:
        actual = by_episode_shot.get((item["episode"], item["shot"]))
        mapping = "episode_shot_fallback"
        warnings.append(
            f'{item["id"]}: SHA mismatch; using episode={item["episode"]}, shot={item["shot"]} '
            f'file {actual["sha256"] if actual else "MISSING"}'
        )
    if actual is None:
        raise RuntimeError(f'missing source for {item["id"]}')
    used.add(actual["path"])
    source_span = float(item["source_end"]) - float(item["source_start"])
    segments.append({
        "id": item["id"],
        "episode": item["episode"],
        "shot": item["shot"],
        "source": actual["path"],
        "source_absolute": str(ROOT / actual["path"]),
        "mapping": mapping,
        "source_sha256": actual["sha256"],
        "declared_sha256": item["sha256"],
        "source_duration": actual["duration"],
        "source_start": item["source_start"],
        "source_end": item["source_end"],
        "source_span": source_span,
        "output_start": item["start"],
        "output_end": item["end"],
        "output_duration": item["duration_output"],
        "fps": actual["fps"],
        "resolution": f'{actual["width"]}x{actual["height"]}',
    })

unused = [item for item in inventory["videos"] if item["path"] not in used]
manifest = {
    "video_count": inventory["video_count"],
    "timeline_count": len(segments),
    "unused_video_count": len(unused),
    "timeline_duration": config["duration"],
    "warnings": warnings,
    "segments": segments,
    "unused_videos": unused,
}
(ROOT / "work/v7_video_timeline.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
with (ROOT / "work/v7_concat_manifest.txt").open("w", encoding="utf-8") as handle:
    for segment in segments:
        handle.write(f'{segment["id"]}\t{segment["source_absolute"]}\t{segment["output_start"]:.6f}\t{segment["output_end"]:.6f}\n')
print(json.dumps({"videos": len(inventory["videos"]), "timeline": len(segments), "unused": len(unused), "warnings": warnings}, ensure_ascii=False))
