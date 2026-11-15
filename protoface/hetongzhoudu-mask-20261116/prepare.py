import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
plan=json.loads((ROOT/'edit-plan.json').read_text());durations=[]
for n in range(1,5):
    ranges=plan[str(n)];parts=[]
    frames=plan.get('target_frames',{}).get(str(n))
    raw_duration=sum(b-a for a,b in ranges)
    pace=(frames/30/raw_duration) if frames else 1
    if not .85<=pace<=1.15:raise ValueError('Adjust edit ranges before pacing')
    for i,(a,b) in enumerate(ranges):
        rect=plan.get('crops',{}).get(str(n),{}).get(str(i))
        crop=('crop='+':'.join(map(str,rect))+',') if rect else ''
        sizing=crop+'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1'
        mute=''.join(f",volume=0:enable='between(t,{max(0,c-a)},{min(b-a,d-a)})'" for c,d in plan.get('mute',{}).get(str(n),[]) if c<b and d>a)
        parts.extend([f'[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,{sizing}[v{i}]',f'[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS{mute}[a{i}]'])
    ins=''.join(f'[v{i}][a{i}]' for i in range(len(ranges)))
    parts.append(f'{ins}concat=n={len(ranges)}:v=1:a=1[vc][ac]')
    vtail=f',tpad=stop_mode=clone:stop_duration=0.12,trim=end_frame={frames}' if frames else ''
    atail=f',apad,atrim=duration={frames/30}' if frames else ''
    parts.append(f'[vc]setpts=PTS*{pace},scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30{vtail}[v]')
    parts.append(f'[ac]atempo={1/pace},aresample=48000,afade=t=in:d=0.025{atail}[a]')
    dst=OUT/f'normalized-{n:02}.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(ROOT/f'scene-{n:02}.mp4'),'-filter_complex',';'.join(parts),'-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(dst)],check=True)
    d=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=duration','-of','json',str(dst)]))
    durations.append(float(d['streams'][0]['duration']))
plan['durations']=durations
(ROOT/'edit-plan.json').write_text(json.dumps(plan,indent=2));print(durations)
