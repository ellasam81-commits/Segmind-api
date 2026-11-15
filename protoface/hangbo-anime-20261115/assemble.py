"""Keep native dialogue timing while joining the three generated fan skit clips."""
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(sys.argv[1] if len(sys.argv)>1 else 'hangbo-anime-output').resolve()
FINAL=ROOT/'T_Hoo_Hoo_TanJianci_Anime_Skit_34s.mp4'

def run(*args):
    subprocess.run(args,check=True,stdout=subprocess.DEVNULL)

def stamp(t):
    h=int(t//3600);m=int(t//60)%60;s=t%60
    return f'{h}:{m:02}:{s:05.2f}'

def main():
    events=json.loads((ROOT/'captions.json').read_text())
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Dialog,Noto Sans CJK SC,33,&H00FFFFFF,&H000000FF,&H00141425,&H70000000,-1,0,0,0,100,100,0,0,1,2,1,2,36,36,30,1
Style: Title,Noto Sans CJK SC,24,&H00FFFFFF,&H000000FF,&H00352228,&H60000000,-1,0,0,0,100,100,0,0,1,1.6,0,7,24,24,19,1
Style: Label,Noto Sans CJK SC,18,&H00FFFFFF,&H000000FF,&H00352228,&H60000000,0,0,0,0,100,100,0,0,1,1.3,0,9,24,24,23,1
Style: End,Noto Sans CJK SC,29,&H00FFFFFF,&H000000FF,&H00352228,&H60000000,-1,0,0,0,100,100,0,0,1,2,1,2,24,24,27,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines=[header,
      'Dialogue: 0,0:00:00.00,0:00:34.25,Title,,0,0,0,,挂播，不是挂起来！',
      'Dialogue: 0,0:00:00.00,0:00:34.25,Label,,0,0,0,,粉丝创作 · 虚构小剧场']
    for e in events:
        lines.append(f"Dialogue: 0,{stamp(e['start'])},{stamp(e['end'])},Dialog,,0,0,0,,{e['text']}")
    lines.append('Dialogue: 1,0:00:32.25,0:00:34.25,End,,0,0,0,,Trouble In My DMs · 檀健次\\N多听歌 · 多分享 · 一起助力')
    ass=ROOT/'captions.ass';ass.write_text('\n'.join(lines)+'\n')
    for i in range(1,4):
        duration=12 if i<3 else 10.25
        start=0 if i<3 else 1.75
        run('ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(start),'-i',str(ROOT/f'scene-{i:02}.mp4'),
            '-vf','scale=1280:720:flags=lanczos,setsar=1,fps=24',
            '-af',f'aresample=48000,loudnorm=I=-16:TP=-1.5:LRA=9,afade=t=in:st=0:d=0.06,afade=t=out:st={duration-0.1}:d=0.1',
            '-t',str(duration),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
            '-c:a','aac','-b:a','192k',str(ROOT/f'normalized-{i:02}.mp4'))
    listing=ROOT/'join.txt';listing.write_text(''.join(f"file 'normalized-{i:02}.mp4'\n" for i in range(1,4)))
    run('ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),
        '-vf','ass='+str(ass),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','192k','-movflags','+faststart',str(FINAL))
    print(FINAL)

if __name__=='__main__':main()
