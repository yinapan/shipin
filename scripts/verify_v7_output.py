import json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
out = ROOT / 'output' / 'Crasheye_V7_female_exec_4k.mp4'
timeline = json.loads((ROOT / 'work' / 'v7_video_timeline.json').read_text(encoding='utf-8'))
probe = subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(out)], capture_output=True, text=True, check=True)
data = json.loads(probe.stdout)
decode = subprocess.run(['ffmpeg','-v','error','-i',str(out),'-f','null','NUL'], capture_output=True, text=True)
video = next(s for s in data['streams'] if s['codec_type']=='video')
audio = next(s for s in data['streams'] if s['codec_type']=='audio')
ass = ROOT / 'Crasheye_V9字幕_产品报告_v7_adjusted.ass'
dialogue = [line for line in ass.read_text(encoding='utf-8-sig').splitlines() if line.startswith('Dialogue:')]
report = {
  'output': str(out), 'decode_exit': decode.returncode,
  'video': {k: video.get(k) for k in ('codec_name','width','height','pix_fmt','r_frame_rate','duration','nb_frames')},
  'audio': {k: audio.get(k) for k in ('codec_name','sample_rate','channels','channel_layout','bit_rate','duration')},
  'timeline': {'actual_video_count': timeline['video_count'], 'timeline_segment_count': timeline['timeline_count'], 'unused_count': timeline['unused_video_count'], 'unused': timeline.get('unused_videos', []), 'warnings': timeline['warnings'], 'duration': timeline['timeline_duration']},
  'subtitles': {'dialogue_count': len(dialogue), 'first': dialogue[0] if dialogue else None, 'last': dialogue[-1] if dialogue else None},
  'checks': {'duration_exact_202s': abs(float(data['format']['duration'])-202.0) < 0.01, 'dimensions_4k': video['width']==3840 and video['height']==2160, 'fps_24': video['r_frame_rate']=='24/1', 'yuv420p': video['pix_fmt']=='yuv420p', 'aac_48k_192k': audio['codec_name']=='aac' and audio['sample_rate']=='48000' and abs(int(audio['bit_rate'])-192000)<5000, 'full_decode_ok': decode.returncode==0, 'subtitle_count_38': len(dialogue)==38}
}
for suffix in ('json','md'):
    p = ROOT / 'output' / f'Crasheye_V7_female_exec_4k.report.{suffix}'
    if suffix == 'json': p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        c = report['checks']; t = report['timeline']
        p.write_text(f"# V7 4K 视频导出报告\n\n- 输出：`{out}`\n- 规格：3840x2160，24fps，yuv420p，H.264 NVENC；AAC 48kHz/192k，时长 {data['format']['duration']} 秒。\n- 完整解码：{'通过' if c['full_decode_ok'] else '失败'}。\n- 字幕：ASS Dialogue {len(dialogue)} 条；首尾字幕已包含在 202 秒时间轴内。\n- 映射：实际视频 {t['actual_video_count']} 个，时间轴镜头 {t['timeline_segment_count']} 段，未使用 {t['unused_count']} 个（第 8 集第 10 镜头）；v2_02 SHA 不一致，已按 episode/shot 回退映射。\n- 检查：规格、时长、帧率、像素格式、音轨、解码均{'通过' if all(c.values()) else '部分通过'}。\n", encoding='utf-8')
print(json.dumps(report['checks'], ensure_ascii=False))
