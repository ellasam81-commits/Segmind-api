"""Re-edit existing animation: short dissolves, synchronized captions and animated gold CTA."""
import array, json, math, random, subprocess, urllib.request, wave
from pathlib import Path

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'; OUT.mkdir(exist_ok=True)
FONT=ROOT/'fonts'; FPS=30; CROSS=4/FPS
FONT.mkdir(exist_ok=True)
font_file=FONT/'MaShanZheng-Regular.ttf'
if not font_file.exists():
    urllib.request.urlretrieve('https://raw.githubusercontent.com/googlefonts/mashanzheng/master/fonts/ttf/MaShanZheng-Regular.ttf',font_file)
D=json.loads((ROOT/'edit-plan.json').read_text())['durations']
OFF=[sum(D[:n])-CROSS*n for n in range(4)]
BODY=sum(D)-CROSS*3
END=BODY+6.8

def sh(args):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode: raise RuntimeError(p.stderr.decode(errors='replace')[-4000:])
def tm(t):
    q=round(t*100);return f'{q//360000}:{q//6000%60:02}:{q//100%60:02}.{q%100:02}'

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
Style: Tag,Noto Sans CJK SC,18,&H00DEE8EF,&H000000FF,&H40221810,&H80000000,0,0,0,0,100,100,1,0,1,0.7,0,9,30,30,38,1
Style: Art,Ma Shan Zheng,108,&H007ACFF5,&H000000FF,&H001B3E65,&H80000000,0,0,0,0,100,100,0,0,1,0.6,0.4,5,0,0,0,1
Style: Text,Noto Sans CJK SC,30,&H00E9F2FF,&H000000FF,&H001C1713,&H80000000,0,0,0,0,100,100,1,0,1,0.6,0,5,0,0,0,1
Style: Shape,Noto Sans CJK SC,20,&H00000000,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
ev=[]
def event(a,b,style,text,layer=0):
    ev.append(f'Dialogue: {layer},{tm(a)},{tm(b)},{style},,0,0,0,,{text}')

event(0,BODY,'Header',r'{\fad(180,260)}何不同舟渡\N{\fnNoto Sans CJK SC\fs18\fsp1}先把药瓶打开',5)
event(0,BODY,'Tag',r'{\fad(180,260)}粉丝二创 · 非正片',5)
caps=json.loads((ROOT/'caption-timing.json').read_text())
for n in range(1,5):
    for a,b,s in caps[str(n)]:
        a+=OFF[n-1];b+=OFF[n-1]
        if s=='水又开了。':
            text=r'{\fnMa Shan Zheng\fs44\1c&H90DEFF&\move(360,1157,360,1145,0,220)\an2\fad(100,100)}'+s
        else:
            s=s.replace('预热',r'{\1c&H8EDFFF&}预热{\1c&HF5F8FF&}').replace('得哄着',r'{\1c&H8EDFFF&}得哄着{\1c&HF5F8FF&}')
            text=r'{\fad(70,100)}'+s
        event(a,min(b,BODY), 'Caption',text,6)

event(OFF[2]+1.83,OFF[2]+3.4,'Text',r'{\pos(360,246)\fnMa Shan Zheng\fs49\1c&H8DDFFF&\fscx80\fscy80\t(0,180,\fscx100\fscy100)\fad(100,180)}尚未开封',7)

# Layered veil fades gradually rather than jumping to a dark freeze frame.
for i in range(32):
    y=i*40;opacity=.12+.73*(i/31)**1.5;alpha=round(255*(1-opacity))
    text=r'{\an7\pos(0,0)\p1\1c&H0B131D&\alpha&H%02X&\fad(900,0)}'%alpha+f'm 0 {y} l 720 {y} 720 {y+40} 0 {y+40}'
    event(BODY,END,'Shape',text,10)

# Very subtle floating ember points echo the flame-haired heroine.
rng=random.Random(407)
for k in range(28):
    x=rng.randrange(45,675);y=rng.randrange(350,1220);radius=rng.choice([1,1,2]);a=BODY+rng.uniform(.1,3.0);b=END
    move=f'\\move({x},{y},{x+rng.randrange(-25,26)},{y-rng.randrange(90,230)})'
    tag='{\\an7'+move+r'\p1\1c&H86D6FF&\bord0\blur1.4\alpha&H55&\fad(600,900)}'
    event(a,b,'Shape',tag+f'm 0 0 l {radius*2} 0 {radius*2} {radius*2} 0 {radius*2}',11)

event(BODY+.35,END,'Text',r'{\fs25\fsp5\1c&HB7D7EF&\move(360,553,360,535,0,500)\fad(450,500)}上药进度：终于开盖',20)

# Staggered brush lettering with soft gold edge light.
letters='何不同舟渡'
for i,ch in enumerate(letters):
    a=BODY+.65+i*.10;x=164+i*98
    motion=f'\\move({x},681,{x},650,0,500)'
    event(a,END,'Art','{'+motion+r'\1c&H3776B7&\bord4\blur8\alpha&H70&\fscx93\fscy93\t(0,500,0.65,\fscx100\fscy100)\fad(320,500)}'+ch,21)
    event(a,END,'Art','{'+motion+r'\1c&H7DD8FF&\blur5\fscx93\fscy93\t(0,500,0.65,\fscx100\fscy100\blur0)\fad(300,500)}'+ch,22)
    shine=f'{{\\pos({x},650)\\1c&HEDFCFF&\\bord0\\blur1\\clip(30,570,110,735)\\t(0,1100,\\clip(620,570,700,735))\\fad(80,150)}}'
    event(BODY+1.8,BODY+3.05,'Art',shine+ch,23)

# Animated divider extends from the center outward.
line=r'{\p1\an7\pos(360,747)\1c&H7AC5E9&\alpha&H50&\fscx0\t(0,650,0.6,\fscx100)\fad(350,500)}m -175 0 l 175 0 175 1 -175 1'
event(BODY+1.35,END,'Shape',line,20)
event(BODY+1.45,END,'Text',r'{\fs31\fsp3\move(360,794,360,777,0,450)\fad(400,500)}檀健次 · 谢却山',20)

pill='m 130 850 l 590 850 b 607 850 620 863 620 880 l 620 920 b 620 937 607 950 590 950 l 130 950 b 113 950 100 937 100 920 l 100 880 b 100 863 113 850 130 850'
event(BODY+2.05,END,'Shape',r'{\p1\an7\move(0,22,0,0,0,500)\1c&H192C43&\alpha&H60&\3c&H59ACEB&\bord2\blur0.4\fad(400,500)}'+pill,20)
event(BODY+2.05,END,'Shape',r'{\p1\an7\move(0,22,0,0,0,500)\1a&HFF&\3c&H3C97E2&\3a&H90&\bord7\blur12\fad(400,500)}'+pill,19)
event(BODY+2.18,END,'Text',r'{\fs39\b1\move(360,921,360,900,0,450)\fad(350,500)\1c&H70BEFF&}芒果 TV{\1c&HECF6FF&} · 立即预约',22)
event(BODY+2.55,END,'Text',r'{\fs26\fsp0.5\move(360,1011,360,993,0,450)\fad(350,500)}打开芒果 TV，搜《何不同舟渡》',20)
event(BODY+2.8,END,'Text',r'{\fs26\fsp1\move(360,1061,360,1043,0,450)\fad(350,500)}进入剧集页，点击「预约」',20)
event(BODY+.3,END,'Text',r'{\pos(360,1200)\fs18\1c&H9BAFBD&\fad(500,500)}粉丝趣味二创 · 非官方物料',20)

ass=OUT/'wordart_v3.ass';ass.write_text(header+'\n'.join(ev)+'\n')
(ROOT/'wordart-timeline.json').write_text(json.dumps({'scene_offsets':OFF,'crossfade_seconds':CROSS,'body_duration':BODY,'duration':END,'booking_url':'https://www.mgtv.com/h/832113.html','booking_instruction':'打开芒果 TV，搜索《何不同舟渡》，进入剧集页点击预约。'},ensure_ascii=False,indent=2))

# A quiet original bell phrase carries the end card after the spoken punchline.
rate=48000
notes=[(.55,587.33,.045),(1.0,880,.03),(1.45,1174.66,.022),(2.12,659.25,.035),(2.55,880,.025)]
samples=array.array('h')
for frame in range(round(6.8*rate)):
    t=frame/rate;sample=0
    for start,freq,amp in notes:
        age=t-start
        if age>=0:
            envelope=min(age/.012,1)*math.exp(-age/1.0)
            sample+=amp*envelope*(math.sin(2*math.pi*freq*age)+.23*math.sin(2*math.pi*freq*2.01*age))
    sample*=min(1,(6.8-t)/.7)
    samples.append(round(max(-1,min(1,sample))*32767))
cue=OUT/'wordart-cue.wav'
with wave.open(str(cue),'wb') as w:
    w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(samples.tobytes())

inputs=[];filters=[]
for n in range(4):
    inputs+=['-i',str(OUT/f'normalized-{n+1:02}.mp4')]
    filters.append(f'[{n}:v]settb=AVTB,setpts=PTS-STARTPTS,fps=30,format=yuv420p[v{n}]')
    filters.append(f'[{n}:a]aresample=48000,apad,atrim=duration={D[n]},asetpts=N/SR/TB[a{n}]')
curv='v0';cura='a0'
for n in range(1,4):
    filters.append(f'[{curv}][v{n}]xfade=transition=fade:duration={CROSS}:offset={OFF[n]}[vx{n}]')
    filters.append(f'[{cura}][a{n}]acrossfade=d={CROSS}:c1=qsin:c2=qsin[ax{n}]')
    curv=f'vx{n}';cura=f'ax{n}'
filters.append(f'[{curv}]tpad=stop_mode=clone:stop_duration=6.8,zoompan=z=\'if(gte(in,{round(BODY*FPS)}),min(zoom+0.00018,1.037),1)\':x=\'iw/2-iw/zoom/2\':y=\'ih/2-ih/zoom/2\':d=1:s=720x1280:fps=30,ass=filename=\'{ass}\':fontsdir=\'{FONT}\',format=yuv420p[vout]')
inputs+=['-i',str(cue)]
filters.append(f'[{cura}]asetpts=N/SR/TB,apad=pad_dur=6.8,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,asetpts=N/SR/TB[amain]')
filters.append(f'[4:a]adelay={round(BODY*1000)}:all=1[cue]')
filters.append('[amain][cue]amix=inputs=2:duration=first:normalize=0[aout]')
draft=OUT/'何不同舟渡_先把药瓶打开_艺术字预约版.mp4'
sh(['ffmpeg','-y',*inputs,'-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[vout]','-map','[aout]','-t',str(END),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(draft)])
print(draft)
