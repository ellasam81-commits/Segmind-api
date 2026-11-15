"""Render the original fan story and a five-second identity/series card."""
import argparse,json,subprocess,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
parser=argparse.ArgumentParser()
parser.add_argument('--masked-photo',type=Path,default=ROOT.parent/'upload/IMG_1883(2).jpeg')
parser.add_argument('--unmasked-photo',type=Path,default=ROOT.parent/'upload/IMG_1869(2).jpeg')
args=parser.parse_args()
for photo in [args.masked_photo,args.unmasked_photo]:
    if not photo.is_file(): raise FileNotFoundError(photo)
FONT=ROOT/'fonts';FONT.mkdir(exist_ok=True)
if not (FONT/'MaShanZheng-Regular.ttf').exists():
    urllib.request.urlretrieve('https://raw.githubusercontent.com/googlefonts/mashanzheng/master/fonts/ttf/MaShanZheng-Regular.ttf',FONT/'MaShanZheng-Regular.ttf')
D=json.loads((ROOT/'edit-plan.json').read_text())['durations'];CROSS=4/30
OFF=[sum(D[:i])-i*CROSS for i in range(4)];BODY=sum(D)-CROSS*3;END=BODY+5
def tm(t):
    x=round(t*100);return f'{x//360000}:{x//6000%60:02}:{x//100%60:02}.{x%100:02}'
header='''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
ScaledBorderAndShadow: yes
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans CJK SC,35,&H00F5F8FF,&H000000FF,&H00241912,&H80000000,-1,0,0,0,100,100,0,0,1,1.8,0.4,2,34,34,125,1
Style: Header,Ma Shan Zheng,35,&H00B6E2FF,&H000000FF,&H60221810,&H80000000,0,0,0,0,100,100,1,0,1,0.5,0.6,7,30,30,34,1
Style: Tag,Noto Sans CJK SC,17,&H00DEE8EF,&H000000FF,&H40221810,&H80000000,0,0,0,0,100,100,0.5,0,1,0.7,0,9,30,30,38,1
Style: Art,Ma Shan Zheng,105,&H007AD5FF,&H000000FF,&H00244464,&H80000000,0,0,0,0,100,100,0,0,1,0.7,0.4,5,0,0,0,1
Style: Text,Noto Sans CJK SC,30,&H00E9F2FF,&H000000FF,&H001C1713,&H80000000,0,0,0,0,100,100,1,0,1,0.7,0,5,0,0,0,1
Style: Shape,Noto Sans CJK SC,20,&H00000000,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
events=[]
def e(a,b,style,text,layer=0):events.append(f'Dialogue: {layer},{tm(a)},{tm(b)},{style},,0,0,0,,{text}')
e(0,BODY-.15,'Header',r'{\fad(150,200)}面具之下\N{\fnNoto Sans CJK SC\fs18\fsp0}何不同舟渡 · 粉丝小剧场',5)
e(0,BODY-.15,'Tag',r'{\fad(150,200)}粉丝原创 · 非官方剧情',5)
caps=json.loads((ROOT/'caption-timing.json').read_text())
for n in range(1,5):
 for a,b,s in caps[str(n)]:
    if s.strip('。！')=='谢却山':
        e(OFF[n-1]+a,min(OFF[n-1]+b+.35,BODY),'Art',r'{\fs68\move(360,1085,360,1065,0,240)\fad(140,160)}谢却山',7)
    else:
        s=s.replace('叛将',r'{\1c&H8EDFFF&}叛将{\1c&HF5F8FF&}')
        e(OFF[n-1]+a,min(OFF[n-1]+b,BODY),'Caption',r'{\fad(70,80)}'+s,7)

# Lower-half gradient leaves the pair visible above the compact title card.
for i in range(32):
    opacity=.10+.83*(i/31)**1.2;alpha=round(255*(1-opacity));y=i*40
    e(BODY-.15,END,'Shape',r'{\an7\pos(0,0)\p1\1c&H161C23&\alpha&H%02X&\fad(300,0)}'%alpha+f'm 0 {y} l 720 {y} 720 {y+40} 0 {y+40}',10)
e(BODY+.05,END,'Text',r'{\fs30\move(360,742,360,726,0,260)\fad(230,220)}背负骂名的他，究竟在守护谁？',20)
for i,ch in enumerate('何不同舟渡'):
    x=164+i*98
    e(BODY+.16+i*.045,END,'Art',f'{{\\move({x},850,{x},829,0,320)\\blur4\\t(0,320,\\blur0)\\fad(220,220)}}'+ch,22)
e(BODY+.3,END,'Text',r'{\pos(360,943)\fs44\fsp2\1c&H97D8FF&\fad(230,220)}檀健次 饰 谢却山',20)
e(BODY+.35,END,'Text',r'{\pos(360,1014)\fs29\1c&H97D8FF&\fad(230,220)}敬请期待 · 芒果 TV 可预约',20)
e(BODY+.05,END,'Text',r'{\pos(360,1200)\fs20\1c&HCBDAE6&\fad(230,220)}粉丝二创 · 动漫剧情非官方',20)
ass=OUT/'story.ass';ass.write_text(header+'\n'.join(events)+'\n')
(ROOT/'wordart-timeline.json').write_text(json.dumps({'scene_offsets':OFF,'body_duration':BODY,'duration':END,'endcard_duration':5,'crossfade_seconds':CROSS},indent=2))
inputs=[];f=[]
for n in range(4):
 inputs+=['-i',str(OUT/f'normalized-{n+1:02}.mp4')]
 f.extend([f'[{n}:v]settb=AVTB,setpts=PTS-STARTPTS,fps=30,format=yuv420p[v{n}]',f'[{n}:a]aresample=48000,apad,atrim=duration={D[n]},asetpts=N/SR/TB[a{n}]'])
v='v0';a='a0'
for n in range(1,4):
 f.extend([f'[{v}][v{n}]xfade=transition=fade:duration={CROSS}:offset={OFF[n]}[vx{n}]',f'[{a}][a{n}]acrossfade=d={CROSS}:c1=qsin:c2=qsin[ax{n}]']);v=f'vx{n}';a=f'ax{n}'
# Two user-supplied actual production photos, not regenerated portraits.
inputs+=['-loop','1','-i',str(args.masked_photo),'-loop','1','-i',str(args.unmasked_photo)]
for idx,length in [(4,3.05),(5,2.8)]:
    f.append(f"[{idx}:v]scale=1440:2560:force_original_aspect_ratio=increase,crop=1440:2560,zoompan=z='min(zoom+0.00018,1.025)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=720x1280:fps=30,trim=duration={length},settb=1/30,setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p[photo{idx}]")
f.append('[photo4][photo5]xfade=transition=fade:duration=0.6:offset=2.45,fps=30,trim=duration=5.25,settb=1/30,setpts=PTS-STARTPTS,fps=30[card]')
f.append(f'[{v}][card]xfade=transition=fade:duration=0.25:offset={BODY-.25},ass=filename=\'{ass}\':fontsdir=\'{FONT}\',format=yuv420p[vout]')
f.append(f'[{a}]asetpts=N/SR/TB,apad=pad_dur=5,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,asetpts=N/SR/TB[aout]')
dst=OUT/'何不同舟渡_面具之下_真人片尾_画面版.mp4'
r=subprocess.run(['ffmpeg','-y',*inputs,'-filter_complex_threads','1','-filter_complex',';'.join(f),'-map','[vout]','-map','[aout]','-t',str(END),'-c:v','libx264','-crf','18','-preset','fast','-c:a','aac','-b:a','192k','-movflags','+faststart',str(dst)],capture_output=True)
if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace')[-4000:])
print(dst)
