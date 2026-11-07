import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
config = json.loads((ROOT / "V7时间轴与单行字幕说明.json").read_text(encoding="utf-8"))
inventory = json.loads((ROOT / "work/asset_inventory.json").read_text(encoding="utf-8"))
by_hash = {item["sha256"]: item for item in inventory["videos"]}
by_episode_shot = {(item["episode"], item["shot"]): item for item in inventory["videos"]}
timeline = config["timeline"]
cues = config["cues"]
timeline_by_id = {item["id"]: item for item in timeline}

issues = []
source_checks = []
for item in timeline:
    actual = by_hash.get(item["sha256"])
    if actual is None:
        actual = by_episode_shot.get((item["episode"], item["shot"]))
        if actual is not None:
            issues.append(
                f'{item["id"]}: source SHA-256 differs from current episode/shot file '
                f'({item["sha256"][:12]} != {actual["sha256"][:12]})'
            )
    if actual is None:
        issues.append(f'{item["id"]}: source SHA-256 not found in asset inventory')
        continue
    source_end = item.get("source_end")
    if source_end is not None and source_end > (actual["duration"] or 0) + 1 / 24:
        issues.append(
            f'{item["id"]}: source_end={source_end:.3f}s exceeds source duration={actual["duration"]:.3f}s'
        )
    source_checks.append(
        {
            "id": item["id"],
            "episode": item["episode"],
            "shot": item["shot"],
            "source_duration": actual["duration"],
            "timeline_duration": item["duration_output"],
            "fps": actual["fps"],
            "resolution": f'{actual["width"]}x{actual["height"]}',
        }
    )

adjusted = []
for cue in cues:
    parent = timeline_by_id.get(cue["unit"])
    if parent is None:
        issues.append(f'{cue["unit"]}: cue has no matching timeline item')
        continue
    start = max(float(cue["start"]), float(parent["start"]))
    end = min(float(cue["end"]), float(parent["end"]))
    if end <= start:
        issues.append(f'{cue["unit"]}: cue has no positive duration after clamping')
        continue
    if start != cue["start"] or end != cue["end"]:
        issues.append(
            f'{cue["unit"]}: clamped cue {cue["start"]:.3f}-{cue["end"]:.3f} '
            f'to shot {start:.3f}-{end:.3f}'
        )
    adjusted.append({**cue, "start": start, "end": end})


def timestamp(seconds, decimal=','):
    total_ms = max(0, round(seconds * 1000))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{decimal}{ms:03d}"


srt = []
for index, cue in enumerate(adjusted, 1):
    srt.append(f'{index}\n{timestamp(cue["start"])} --> {timestamp(cue["end"])}\n{cue["caption_text"]}\n')
(ROOT / "Crasheye_V9字幕_产品报告_v7_adjusted.srt").write_text("\n".join(srt), encoding="utf-8")

ass_header = """[Script Info]\nScriptType: v4.00+\nPlayResX: 3840\nPlayResY: 2160\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Microsoft YaHei,112,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80101010,0,0,0,0,100,100,0,0,1,5,2,2,120,120,155,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
dialogues = []
for cue in adjusted:
    text = str(cue["caption_text"]).replace("\n", "\\N")
    dialogues.append(
        f'Dialogue: 0,{timestamp(cue["start"], ".")[:-1]},{timestamp(cue["end"], ".")[:-1]},Default,,0,0,0,,{text}'
    )
(ROOT / "Crasheye_V9字幕_产品报告_v7_adjusted.ass").write_text(ass_header + "\n".join(dialogues) + "\n", encoding="utf-8-sig")

report = {
    "source_json": str(ROOT / "V7时间轴与单行字幕说明.json"),
    "video_count": inventory["video_count"],
    "timeline_count": len(timeline),
    "cue_count": len(cues),
    "adjusted_cue_count": len(adjusted),
    "issues": issues,
    "source_checks": source_checks,
    "outputs": [
        str(ROOT / "Crasheye_V9字幕_产品报告_v7_adjusted.ass"),
        str(ROOT / "Crasheye_V9字幕_产品报告_v7_adjusted.srt"),
    ],
}
(ROOT / "V7时间轴_字幕调整报告.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(ROOT / "V7时间轴_字幕调整报告.md").write_text(
    "# V7 字幕时间调整报告\n\n"
    f'- 实际视频：{inventory["video_count"]} 个；时间轴镜头：{len(timeline)} 个；字幕：{len(cues)} 条。\n'
    f'- 输出字幕：{len(adjusted)} 条，均限制在对应镜头的 start/end 边界内。\n'
    f'- 发现问题：{len(issues)} 项。\n\n'
    + ("\n".join(f"- {issue}" for issue in issues) if issues else "未发现越界或缺失映射。")
    + "\n",
    encoding="utf-8",
)
print(json.dumps({"videos": inventory["video_count"], "timeline": len(timeline), "cues": len(cues), "adjusted": len(adjusted), "issues": len(issues)}, ensure_ascii=False))
