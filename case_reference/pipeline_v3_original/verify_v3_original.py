from pathlib import Path
import json, hashlib, re
import av
import imageio_ffmpeg
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'work'/'revision_v3_original'
O=ROOT/'output'/'full_story_v6_v3_20261107'
target=O/'Crasheye_完整故事_4K_V3_原画恢复.mp4'
meta=json.loads((W/'timeline.json').read_text(encoding='utf-8'))

def order(p):
    return (int(re.search(r'第(\d+)集',p.relative_to(ROOT/'mp4').parts[0]).group(1)), int(re.search(r'shot(\d+)',p.name).group(1)), p.name)

files=sorted((ROOT/'mp4').rglob('*.mp4'),key=order)
assert len(files)==38 and sum(order(p)[0]==2 for p in files)==1
assert [str(p.relative_to(ROOT)) for p in files]==[t['original_path'] for t in meta['timeline']]
for p,t in zip(files,meta['timeline']): assert hashlib.sha256(p.read_bytes()).hexdigest()==t['sha256']
for t in meta['timeline']:
    c=av.open(str(W/'retimed'/f"clip_{t['index']:02d}.mp4")); count=sum(1 for _ in c.decode(video=0)); c.close(); assert count==t['frames']

c=av.open(str(target)); vs=c.streams.video[0]; aud=c.streams.audio[0]; frames=sum(1 for _ in c.decode(video=0)); c.close()
assert (vs.width,vs.height)==(3840,2160) and round(float(vs.average_rate))==24 and frames==meta['frames']
c=av.open(str(target)); audio_samples=sum(f.samples for f in c.decode(audio=0)); c.close(); assert audio_samples>int((meta['duration']-.1)*48000)
slow=meta['timeline'][15]; assert slow['index']==16 and slow['speech_duration']>5.0 and meta['slow_factor']==.82
report={'file':str(target),'width':vs.width,'height':vs.height,'fps':24,'duration':meta['duration'],'frames':frames,'source_count':38,'episode2_count':1,'visual_policy':meta['visual_policy'],'slow_segment':{'index':16,'text':slow['text'],'start':slow['start'],'end':slow['end'],'speech_duration':slow['speech_duration'],'factor':meta['slow_factor']},'full_decode':'video and audio decoded successfully','source_order_verified':True,'original_source_hashes_verified':True}
(O/'核验报告.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'交付与核验说明.md').write_text(f"# V3 交付与核验\n\n成片：`{target.name}`；3840×2160、24fps、{meta['duration']:.3f}秒。\n\n- 38个镜头按第1集至第12集、集内shot数字顺序核对；第2集为1个镜头。\n- 所有画面直接使用当前原始视频；已去除上版新增的文字修复、重绘对话框和裁切。\n- 只添加沉稳高管旁白与字幕。\n- 第16段“就像急诊接诊，把同类症状整理到一起”单独使用0.82倍速度，语音时长{slow['speech_duration']:.3f}秒；其他段落保持原V2旁白节奏。\n- 视频完整解码，音频完整读取，4K规格核对通过。\n",encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
