from pathlib import Path
import json, hashlib, subprocess, av
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]; W=ROOT/'work'/'revision_v3_original'; O=ROOT/'output'/'full_story_v6_v3_20261107'; D=W/'retimed'; D.mkdir(exist_ok=True)
F=imageio_ffmpeg.get_ffmpeg_exe(); meta=json.loads((W/'timeline.json').read_text(encoding='utf-8')); playlist=[]
for t in meta['timeline']:
    src=Path(t['path']); dest=D/f"clip_{t['index']:02d}.mp4"; marker=dest.with_suffix('.json')
    sig=hashlib.sha256(src.read_bytes()+json.dumps(t,sort_keys=True).encode()).hexdigest()
    if not dest.exists() or not marker.exists() or json.loads(marker.read_text())['signature']!=sig:
        factor=t['duration_output']/(t['source_end']-t['source_start'])
        vf=f"tpad=stop_mode=clone:stop_duration=0.20,trim=start={t['source_start']}:end={t['source_end']+.18},setpts={factor}*(PTS-STARTPTS)"
        if factor>1.08: vf+=',minterpolate=fps=24:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:search_param=16'
        else: vf+=',fps=24'
        with (D/f"{t['index']:02d}.log").open('w') as log:
            subprocess.run([F,'-hide_banner','-y','-i',str(src),'-vf',vf,'-frames:v',str(t['frames']),'-an','-c:v','libx264','-preset','fast','-crf','13',str(dest)],stdout=log,stderr=log,check=True)
        c=av.open(str(dest)); count=sum(1 for _ in c.decode(video=0)); c.close(); assert count==t['frames']
        marker.write_text(json.dumps({'signature':sig}))
    playlist.append("file '"+dest.as_posix()+"'")
(W/'concat.txt').write_text('\n'.join(playlist),encoding='utf-8')
out=O/'Crasheye_完整故事_4K_V3_原画恢复.mp4'
cmd=[F,'-hide_banner','-y','-f','concat','-safe','0','-i',str(W/'concat.txt'),'-i',str(O/'Crasheye_V3_原画恢复旁白.wav'),'-vf','scale=3840:2160:flags=lanczos,unsharp=5:5:0.35:5:5:0,ass=work/revision_v3_original/subtitles.ass','-map','0:v','-map','1:a','-c:v','h264_nvenc','-preset','p7','-tune','hq','-rc','vbr','-cq','17','-b:v','0','-spatial-aq','1','-temporal-aq','1','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-ac','2','-b:a','192k','-movflags','+faststart','-progress',str(W/'render_progress.txt'),'-nostats',str(out)]
with (W/'render.log').open('w') as log: subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=log,check=True)
print('V3 export finished:',out)
