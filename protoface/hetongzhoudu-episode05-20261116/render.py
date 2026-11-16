"""45-second fan film; native dialogue, aligned subtitles, supplied music and real-photo ending."""
from pathlib import Path
import json,subprocess,math
import numpy as np
from scipy.io import wavfile
from scipy import signal
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output';OUT.mkdir(exist_ok=True);GEN=ROOT/'generated';ASSETS=ROOT/'assets';RATE=48000;FPS=30
OFFSETS=[0,8,16,24,31];DURS=[8+4/30,8+4/30,8+4/30,7+4/30,8];CUT=.2;TOTAL=45;BODY=37.1

def sh(c):
 r=subprocess.run(c,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-3500:])
def tm(t):
 q=round(t*100);return f'{q//360000}:{q//6000%60:02}:{q//100%60:02}.{q%100:02}'
def prepare():
 clips=[]
 for i,d in enumerate(DURS,1):
  dst=OUT/f'normalized-{i:02}.mp4';src=GEN/f'scene-{i:02}.mp4';frames=round(d*30)
  sh(['ffmpeg','-v','error','-y','-ss',str(CUT),'-i',str(src),'-vf',f'scale=720:1280:force_original_aspect_ratio=increase:out_range=tv,crop=720:1280,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=1.0,trim=end_frame={frames},settb=1/30,setpts=N/(30*TB),format=yuv420p','-af',f'aresample=48000,apad,atrim=duration={d},asetpts=PTS-STARTPTS','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-r','30','-fps_mode','cfr','-video_track_timescale','30000','-c:a','aac','-b:a','192k','-t',str(d),str(dst)]);clips.append(dst)
 f=[];args=[]
 for i,p in enumerate(clips):args+=['-i',str(p)];f.append(f'[{i}:v]settb=1/30,setpts=PTS-STARTPTS,fps=30[v{i}]');f.append(f'[{i}:a]asetpts=PTS-STARTPTS[a{i}]')
 v='v0';a='a0'
 for i in range(1,5):
  f.append(f'[{v}][v{i}]xfade=transition=fade:duration={4/30}:offset={OFFSETS[i]}[v{i}x]');v=f'v{i}x'
  f.append(f'[{a}][a{i}]acrossfade=d={4/30}:c1=qsin:c2=qsin[a{i}x]');a=f'a{i}x'
 f.append(f'[{v}]fps=30,trim=end_frame=1170,settb=1/30,setpts=N/(30*TB),format=yuv420p[v]')
 sh(['ffmpeg','-v','error','-y',*args,'-filter_complex_threads','1','-filter_complex',';'.join(f),'-map','[v]','-map',f'[{a}]','-c:v','libx264','-threads','3','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-r','30','-fps_mode','cfr','-enc_time_base:v','1:30','-video_track_timescale','30000','-c:a','aac','-b:a','192k','-t','39',str(OUT/'body.mp4')])
def revise_body():
 src=OUT/'body.mp4';dst=OUT/'body_revised.mp4'
 filt='[0:v]split=2[v0][v1];[v0]trim=end=17.8,setpts=PTS-STARTPTS[a];[v1]trim=start=19.7,setpts=PTS-STARTPTS[b];[0:a]asplit=2[a0][a1];[a0]atrim=end=17.8,asetpts=PTS-STARTPTS[c];[a1]atrim=start=19.7,asetpts=PTS-STARTPTS[d];[a][c][b][d]concat=n=2:v=1:a=1[v][au]'
 sh(['ffmpeg','-v','error','-y','-i',str(src),'-filter_complex',filt,'-map','[v]','-map','[au]','-c:v','libx264','-threads','3','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-pix_fmt','yuv420p','-r','30','-video_track_timescale','30000','-c:a','aac','-b:a','192k',str(dst)])
 dst.replace(src)
def audio(p,n=TOTAL*RATE):
 b=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-t',str(TOTAL),'-ac','2','-ar',str(RATE),'-f','f32le','pipe:1']);x=np.frombuffer(b,dtype=np.float32).reshape(-1,2);return np.pad(x[:n],((0,max(0,n-len(x))),(0,0)))
def ease(t):return .5-.5*np.cos(np.pi*np.clip(t,0,1))
def mix(captions):
 n=TOTAL*RATE;t=np.arange(n)/RATE;voice=audio(OUT/'body.mp4');music=audio(ASSETS/'幻火.mp3')
 music=signal.sosfilt(signal.butter(2,60,fs=RATE,btype='highpass',output='sos'),music,axis=0)
 b,a=signal.iirpeak(2200,.7,fs=RATE);music-=.35*signal.lfilter(b,a,music,axis=0)
 speech=np.zeros(n)
 for start,end,_ in captions:speech=np.maximum(speech,ease((t-start+.15)/.12)*(1-ease((t-end-.04)/.25)))
 rms=[];centers=[]
 for s in range(0,n,RATE):rms.append(np.sqrt(np.mean(music[s:s+RATE]**2)+1e-12));centers.append((s+RATE/2)/RATE)
 level=np.interp(t,centers,rms);outro=ease((t-37.1)/.5);target=(-25-8*speech)*(1-outro)-22*outro
 gain=np.clip(10**(target/20)/np.maximum(level,.03),.02,1)*ease(t/.5)*(1-ease((t-43.5)/1.5));music*=gain[:,None]
 fx=np.zeros((n,2));rng=np.random.default_rng(20261116)
 def sound(at,duration,kind,db):
  tt=np.arange(round(duration*RATE))/RATE;noise=signal.sosfilt(signal.butter(2,[150,3600],btype='bandpass',fs=RATE,output='sos'),rng.normal(size=len(tt)))
  if kind=='fire':wave=noise*np.sin(np.pi*tt/duration)**2
  else:wave=noise*np.sin(np.pi*tt/duration)**3
  wave=wave/max(abs(wave).max(),1e-6)*10**(db/20);k=round(at*RATE);fx[k:k+len(wave)]+=wave[:,None]*.707
 sound(14.5,.22,'fire',-31);sound(36.95,.45,'air',-34)
 x=voice+music+fx;wavfile.write(OUT/'mix.wav',RATE,x.astype(np.float32))
 return OUT/'mix.wav'
def subtitles(captions):
 header='''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
ScaledBorderAndShadow: yes
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,Noto Sans CJK SC,34,&H00F5F8FF,&H000000FF,&H00231915,&H80000000,-1,0,0,0,100,100,0,0,1,1.8,0.3,2,36,36,125,1
Style: Header,Noto Serif CJK SC,29,&H009DE4FF,&H000000FF,&H00231915,&H80000000,-1,0,0,0,100,100,1,0,1,0.8,0,7,28,28,34,1
Style: Tag,Noto Sans CJK SC,16,&H00DEE8EF,&H000000FF,&H00231915,&H80000000,0,0,0,0,100,100,0,0,1,0.7,0,9,28,28,38,1
Style: Art,Noto Serif CJK SC,94,&H007DD8FF,&H000000FF,&H00274464,&H80000000,-1,0,0,0,100,100,0,0,1,0.7,0.5,5,0,0,0,1
Style: Text,Noto Sans CJK SC,32,&H00E9F2FF,&H000000FF,&H001C1713,&H80000000,0,0,0,0,100,100,0,0,1,0.8,0,5,0,0,0,1
Style: Shape,Noto Sans CJK SC,20,&H00000000,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
 ev=[]
 def e(a,b,style,txt,layer=1):ev.append(f'Dialogue: {layer},{tm(a)},{tm(b)},{style},,0,0,0,,{txt}')
 e(0,36.8,'Header',r'{\fad(160,180)}将军，你是不是坏人？\N{\fnNoto Sans CJK SC\fs17\fsp0}何不同舟渡 · 粉丝小剧场')
 e(0,36.8,'Tag',r'{\fad(160,180)}AI辅助创作 · 非官方剧情')
 for a,b,txt in captions:e(a,b,'Caption',r'{\fad(60,80)}'+txt,5)
 for j in range(32):
  alpha=round(255*(1-(.08+.84*(j/31)**1.3)));y=j*40
  e(36.95,45,'Shape',r'{\an7\pos(0,0)\p1\1c&H131C24&\alpha&H%02X&\fad(350,0)}'%alpha+f'm 0 {y} l 720 {y} 720 {y+40} 0 {y+40}',10)
 e(37.2,45,'Text',r'{\fs30\move(360,758,360,738,0,350)\fad(240,250)}他背负的骂名，藏着谁的生路？',20)
 for j,ch in enumerate('何不同舟渡'):e(37.3+j*.05,45,'Art',f'{{\\move({160+j*100},862,{160+j*100},838,0,350)\\blur3\\t(0,350,\\blur0)\\fad(250,220)}}'+ch,22)
 e(37.5,45,'Text',r'{\pos(360,954)\fs40\fsp1\1c&H9DDCFF&\fad(230,250)}檀健次 饰 谢却山',20)
 e(37.2,45,'Text',r'{\pos(360,1198)\fs20\1c&HCFDDE6&\fad(230,250)}AI辅助创作 · 粉丝二创 · 非官方剧情',20)
 p=OUT/'film.ass';p.write_text(header+'\n'.join(ev)+'\n');return p

def finish():
 captions=json.loads((ROOT/'captions.json').read_text());wav=mix(captions);ass=subtitles(captions)
 f=[]
 for i,d in [(1,5.7),(2,3.1)]:f.append(f"[{i}:v]scale=1440:2560:force_original_aspect_ratio=increase:out_range=tv,crop=1440:2560,zoompan=z='min(zoom+0.00012,1.03)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=720x1280:fps=30,trim=duration={d},settb=1/30,setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p[p{i}]")
 f+=['[p1][p2]xfade=transition=fade:duration=0.6:offset=5.1,trim=duration=8.2,settb=1/30,setpts=PTS-STARTPTS,fps=30[card]','[0:v]settb=1/30,setpts=PTS-STARTPTS,fps=30[body]',f"[body][card]xfade=transition=fade:duration=0.3:offset=36.8,ass=filename='{ass}',fps=30,tpad=stop_mode=clone:stop_duration=0.1,trim=end_frame=1350,settb=1/30,setpts=N/(30*TB),format=yuv420p[v]"]
 dst=OUT/'XieQueshan_05_AreYouAVillain.mp4'
 sh(['ffmpeg','-v','error','-y','-i',str(OUT/'body.mp4'),'-loop','1','-framerate','30','-i',str(ASSETS/'end_mask.png'),'-loop','1','-framerate','30','-i',str(ASSETS/'end_sword.png'),'-i',str(wav),'-filter_complex_threads','1','-filter_complex',';'.join(f),'-map','[v]','-map','3:a','-c:v','libx264','-threads','3','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-tag:v','avc1','-maxrate','6000k','-bufsize','12000k','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-r','30','-fps_mode','cfr','-enc_time_base:v','1:30','-video_track_timescale','30000','-af','loudnorm=I=-16:TP=-1.5:LRA=11','-ar','48000','-ac','2','-c:a','aac','-b:a','192k','-t','45','-movflags','+faststart',str(dst)])
 print(dst,flush=True)
if __name__=='__main__':
 import sys
 if sys.argv[1]=='prepare':
  prepare()
  revise_body()
 else:finish()
