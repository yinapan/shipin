from pathlib import Path
import json, math, re, subprocess
import numpy as np
import soundfile as sf
import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
W=ROOT/'work'/'revision_v3_original'
O=ROOT/'output'/'full_story_v6_v3_20261107'
W.mkdir(exist_ok=True); O.mkdir(exist_ok=True)
old=json.loads((ROOT/'work'/'revision_v2'/'timeline.json').read_text(encoding='utf-8'))
FF=imageio_ffmpeg.get_ffmpeg_exe()
N=ROOT/'work'/'revision_v2'/'voice_normalized'
parts=[]; timeline=[]; cues=[]; cursor=0.0

def at(t):
    x=round(t*100); return f'{x//360000}:{x//6000%60:02}:{x//100%60:02}.{x%100:02}'
def st(t):
    x=round(t*1000); return f'{x//3600000:02}:{x//60000%60:02}:{x//1000%60:02},{x%1000:03}'

for base in old['timeline']:
    i=base['index']; source=ROOT/base['original_path']
    voice=N/(base['id']+'.wav')
    # The user identified this sentence as too fast. Slow only this sentence,
    # preserving its pitch and leaving every other narration unit unchanged.
    if i==16:
        slowed=W/'v3_16_slow.wav'
        subprocess.run([FF,'-v','error','-y','-i',str(voice),'-af','atempo=0.82,aresample=48000,asetpts=N/SR/TB','-ar','48000','-ac','1',str(slowed)],check=True)
        voice=slowed
    data,sr=sf.read(str(voice),dtype='float32')
    length=len(data)/sr; duration=math.ceil((.20+length+.22)*24)/24; frames=round(duration*24)
    audio=np.zeros(round(duration*48000),np.float32); audio[9600:9600+len(data)]=data; parts.append(audio)
    cues.append({'unit':base['id'],'index':i,'start':cursor+.20,'end':cursor+.20+length,'text':base['text']})
    t={**base,'path':str(source),'original_path':str(source.relative_to(ROOT)),'start':cursor,'end':cursor+duration,
       'frames':frames,'duration_output':duration,'voice_file':str(voice.relative_to(ROOT)),'speech_duration':length,
       'visual_source':'original_restored','visual_edits':[]}
    timeline.append(t); cursor+=duration

sf.write(str(O/'Crasheye_V3_原画恢复旁白.wav'),np.concatenate(parts),48000)
header=(ROOT/'work'/'revision_v2'/'subtitles.ass').read_text(encoding='utf-8-sig').split('[Events]')[0]
ass=header+'[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n'
for c in cues:
    text=re.sub('软件崩溃|闪退|人工智能|工程师|更快定位|更准分析|更多精力留给修复|八项专利',lambda m:r'{\c&H0000BFFF&\b1}'+m.group()+r'{\c&H00FFFFFF&\b0}',c['text'])
    ass+=f"Dialogue: 1,{at(c['start'])},{at(c['end'])},Default,,0,0,0,,{text}\n"
ass+='Dialogue: 0,0:00:00.20,0:00:06.20,Note,,0,0,0,,除片尾资质信息外，本片数据和案例均为演示示意，不代表实测结果。\n'
(W/'subtitles.ass').write_text(ass,encoding='utf-8-sig'); (O/'Crasheye_V3字幕.ass').write_text(ass,encoding='utf-8-sig')
(O/'Crasheye_V3字幕.srt').write_text(''.join(f"{i}\n{st(c['start'])} --> {st(c['end'])}\n{c['text']}\n\n" for i,c in enumerate(cues,1)),encoding='utf-8-sig')
meta={'duration':cursor,'frames':sum(t['frames'] for t in timeline),'source_count':len(timeline),'timeline':timeline,'cues':cues,
      'voice_style':'沿用V2沉稳高管声线；仅第16段“就像急诊接诊”放慢','visual_policy':'恢复原始视频画面，只添加旁白和字幕','slow_unit':16,'slow_factor':0.82}
(W/'timeline.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'新版时间轴与语速.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
(O/'画面处理说明.md').write_text('# V3 画面处理说明\n\n本版回滚上次画面文字修复与重绘面板，38个镜头直接使用原始视频文件；成片只新增旁白和字幕。第16段“就像急诊接诊，把同类症状整理到一起。”使用0.82倍语速处理，其他旁白保持V2声线和时长。\n',encoding='utf-8')
print(f'V3 original-image timeline: {cursor:.3f}s; slow unit 16 only.')
