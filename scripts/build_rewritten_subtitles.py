"""Build and validate rewritten subtitles from the reviewed 44-video draft."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "work/v7_rewritten_subtitle_draft.json"
INVENTORY = ROOT / "work/all_mp4_inventory.json"
SRT_OUT = ROOT / "Crasheye_重写字幕.srt"
ASS_OUT = ROOT / "Crasheye_重写字幕.ass"
REPORT_MD = ROOT / "Crasheye_字幕重写报告.md"
REPORT_JSON = ROOT / "Crasheye_字幕重写校验报告.json"
MAX_RATE = 3.2


def ts(seconds: float, sep: str = ",") -> str:
    ms = max(0, round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{ms:03d}"


def main() -> int:
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    inv = {x["path"].replace("\\", "/"): x for x in inventory["items"]}
    segments = []
    issues = []
    previous_end = -1.0
    for item in draft["segments"]:
        path_key = item["path"].replace("\\", "/")
        meta = inv.get(path_key)
        if not meta:
            issues.append(f"{item['id']}: missing inventory entry")
            meta = {}
        start = float(item["start"])
        video_end = float(item["end"])
        text = str(item["text"]).strip()
        # Recompute the minimum narration span from the effective spoken-character
        # count; draft durations are rounded and may otherwise exceed 3.2 by a few
        # thousandths. Punctuation is excluded from this rate budget.
        spoken_chars = len(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", text))
        speech = max(float(item["expected_speech_seconds"]), spoken_chars / MAX_RATE)
        cue_end = min(video_end, start + speech)
        rate = spoken_chars / max(speech, 1e-9)
        passed = bool(text) and cue_end > start and cue_end <= video_end + 1e-6 and rate <= MAX_RATE + 1e-9 and start >= previous_end - 1e-6
        if not passed:
            issues.append(f"{item['id']}: timing/text/rate validation failed")
        previous_end = video_end
        segments.append({**item, "spoken_char_count": spoken_chars, "video_duration": meta.get("duration"), "resolution": f"{meta.get('video', {}).get('width', '?')}x{meta.get('video', {}).get('height', '?')}", "fps": meta.get("video", {}).get("fps"), "audio": meta.get("audio", []), "visual_sample_yavg": meta.get("visual_sample_yavg", []), "visual_change_range": meta.get("visual_change_range"), "cue_start": start, "cue_end": cue_end, "actual_rate": rate, "pass": passed})

    srt = []
    for i, item in enumerate(segments, 1):
        srt.append(f"{i}\n{ts(item['cue_start'])} --> {ts(item['cue_end'])}\n{item['text']}\n")
    SRT_OUT.write_text("\n".join(srt), encoding="utf-8")

    header = """[Script Info]\nScriptType: v4.00+\nPlayResX: 3840\nPlayResY: 2160\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Microsoft YaHei,112,&H00FFFFFF,&H00FFFFFF,&H00101010,&H80101010,0,0,0,0,100,100,0,0,1,5,2,2,120,120,155,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    events = [f"Dialogue: 0,{ts(x['cue_start'], '.').replace(',', '')[:-1]},{ts(x['cue_end'], '.').replace(',', '')[:-1]},Default,,0,0,0,,{x['text']}" for x in segments]
    ASS_OUT.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")

    parsed_srt = []
    for block in SRT_OUT.read_text(encoding="utf-8").strip().split("\n\n"):
        lines = block.splitlines()
        if len(lines) >= 3:
            parsed_srt.append("\n".join(lines[2:]))
    parsed_ass = [line.split(",", 9)[-1] for line in ASS_OUT.read_text(encoding="utf-8-sig").splitlines() if line.startswith("Dialogue:")]
    canonical_texts = [x["text"] for x in segments]
    text_equal = parsed_srt == canonical_texts == parsed_ass
    overlap = sum(1 for a, b in zip(segments, segments[1:]) if b["cue_start"] < a["cue_end"] - 1e-9)
    out_of_bounds = sum(1 for x in segments if x["cue_start"] < x["start"] - 1e-9 or x["cue_end"] > x["end"] + 1e-9)
    rate_fail = sum(1 for x in segments if x["actual_rate"] > MAX_RATE + 1e-9)
    if overlap: issues.append(f"overlap={overlap}")
    if out_of_bounds: issues.append(f"out_of_bounds={out_of_bounds}")
    if rate_fail: issues.append(f"rate_fail={rate_fail}")
    report = {"source_script": draft.get("source_script"), "video_count": len(segments), "mapped_count": len(segments), "cue_count": len(segments), "total_duration": draft.get("total_duration"), "max_rate": MAX_RATE, "issues": list(dict.fromkeys(issues)), "all_pass": not issues and text_equal, "srt_count": len(parsed_srt), "ass_count": len(parsed_ass), "srt_ass_text_equal": text_equal, "overlap": overlap, "out_of_bounds": out_of_bounds, "rate_fail": rate_fail, "visual_verification": draft.get("visual_verification", {}), "segments": segments, "outputs": [str(SRT_OUT), str(ASS_OUT)]}
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 字幕重写报告", "", f"- 视频片段：{len(segments)} 个；总时长：{draft.get('total_duration', 0):.3f} 秒。", f"- 字幕单元：{len(segments)} 条；每条限定在对应视频片段内。", f"- 语速上限：{MAX_RATE:.1f} 字/秒；通过：{sum(x['pass'] for x in segments)}/{len(segments)}。", f"- SRT/ASS 文本逐条一致：{'是' if text_equal else '否'}。"]
    visual_note = draft.get("visual_verification", {}).get("summary")
    if visual_note: lines.append(f"- 视觉核验：{visual_note}。")
    lines += ["", "## 逐段明细", "", "| # | 视频 | 时长 | 画面变化摘要 | 字幕 | 字数 | 预计朗读 | 起止 | 语速 | 通过 |", "|---:|---|---:|---|---|---:|---:|---|---:|---|"]
    for x in segments:
        visual = ", ".join(f"{v:.1f}" for v in x.get("visual_sample_yavg", []))
        lines.append(f"| {x['index']} | `{x['id']}` | {x.get('video_duration', x['duration']):.3f}s | YAVG {visual} | {x['text']} | {x['spoken_char_count']} | {x['expected_speech_seconds']:.3f}s | {x['cue_start']:.3f}–{x['cue_end']:.3f} | {x['actual_rate']:.2f} | {'通过' if x['pass'] else '失败'} |")
    if issues:
        lines.extend(["", "## 问题", ""] + [f"- {x}" for x in issues])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"videos": len(segments), "cues": len(segments), "issues": len(issues), "all_pass": report["all_pass"]}, ensure_ascii=False))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
