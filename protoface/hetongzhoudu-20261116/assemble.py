import json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
def sh(args): subprocess.run(args,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
def tm(t):
    c=round(t*100);return f'{c//360000}:{c//6000%60:02}:{c//100%60:02}.{c%100:02}'

scenes=json.loads((ROOT/'scenes.json').read_text())['scenes']
overrides=json.loads((ROOT/'caption-timing.json').read_text()) if (ROOT/'caption-timing.json').exists() else {}
header='''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans CJK SC,35,&H00FAFAFA,&H000000FF,&H00241912,&H80000000,-1,0,0,0,100,100,0,0,1,2,0.5,2,38,38,125,1
Style: Title,Noto Serif CJK SC,34,&H009DDDF7,&H000000FF,&H40271C14,&H80000000,-1,0,0,0,100,100,2,0,1,1,1,7,32,32,38,1
Style: Tag,Noto Sans CJK SC,19,&H00E8E8E8,&H000000FF,&H40271C14,&H80000000,0,0,0,0,100,100,1,0,1,1,0,9,30,32,43,1
Style: EndTitle,Noto Serif CJK SC,67,&H00B3DEF7,&H000000FF,&H00221912,&H80000000,-1,0,0,0,100,100,4,0,1,1,1,5,25,25,0,1
Style: EndSub,Noto Sans CJK SC,29,&H00F4F4F4,&H000000FF,&H00221912,&H80000000,0,0,0,0,100,100,2,0,1,1,0,5,30,30,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
events=[]
def event(a,b,style,text,layer=0): events.append(f'Dialogue: {layer},{tm(a)},{tm(b)},{style},,0,0,0,,{text}')
event(0,48,'Title','何不同舟渡')
event(0,48,'Tag','粉丝二创 · 非正片')
for s in scenes:
    lines=overrides.get(str(s['n']),s['captions'])
    for a,b,text in lines:
        if len(text)>18:
            text=text.replace('》预热','》\\N预热').replace('》预热','》\\N预热')
        event((s['n']-1)*12+a,(s['n']-1)*12+b,'Caption',text)
event(48,51.5,'EndTitle',r'{\pos(360,540)\fad(300,300)}何不同舟渡')
event(48.2,51.5,'EndSub',r'{\pos(360,642)\fad(300,300)}期待檀健次 · 谢却山')
event(48.4,51.5,'EndSub',r'{\pos(360,720)\fs25\fad(300,300)}小炭火已就位，等你同舟。')
event(48.4,51.5,'EndSub',r'{\pos(360,1110)\fs19\fad(300,300)}粉丝趣味二创 · 非剧集正片')
(OUT/'subtitles.ass').write_text(header+'\n'.join(events)+'\n')
for n in range(1,5):
    src=ROOT/f'scene-{n:02}.mp4';dst=OUT/f'normalized-{n:02}.mp4'
    sh(['ffmpeg','-y','-i',str(src),'-filter_complex',
        '[0:v]trim=duration=12,setpts=PTS-STARTPTS,scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30[v];[0:a]atrim=duration=12,asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.06,afade=t=out:st=11.88:d=0.12[a]',
        '-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',str(dst)])
(OUT/'concat.txt').write_text(''.join("file '"+str(OUT/f'normalized-{n:02}.mp4')+"'\n" for n in range(1,5)))
sh(['ffmpeg','-y','-f','concat','-safe','0','-i',str(OUT/'concat.txt'),'-c','copy',str(OUT/'assembled.mp4')])
final=OUT/'何不同舟渡_小炭火上药记_动漫二创.mp4'
vf=f"tpad=stop_mode=clone:stop_duration=3.5,drawbox=x=0:y=0:w=iw:h=ih:color=black@0.58:t=fill:enable='gte(t,48)',ass='{OUT/'subtitles.ass'}'"
sh(['ffmpeg','-y','-i',str(OUT/'assembled.mp4'),'-vf',vf,'-af','apad=pad_dur=3.5,loudnorm=I=-16:TP=-1.5:LRA=11','-t','51.5','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(final)])
print(final)
