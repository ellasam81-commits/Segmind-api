"""Replace only the unclear action, preserve dialogue and actual-photo ending."""
import json,subprocess,importlib.util
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy import signal
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent;OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('cards',BASE/'douyin-endcards/rewrite_endcards.py');cards=importlib.util.module_from_spec(spec);spec.loader.exec_module(cards)
SRC=BASE/'hetongzhoudu-mask/output/XieQueshan_iPhone.mp4';ACTION=ROOT/'generated/mask-action-tight.mp4'
START=797;END=938;TOTAL=1283;RATE=48000

def command(c):
 r=subprocess.run(c,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-3000:])
def audio(path):
 b=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-ac','2','-ar',str(RATE),'-f','f32le','pipe:1']);return np.frombuffer(b,dtype=np.float32).reshape(-1,2).copy()
def render():
 if not ACTION.exists():
  source=ROOT/'generated/mask-action-repaired.mp4';ranges=[(0,40),(53,55),(71,87),(100,120),(123,158)];filters=[]
  for n,(a,b) in enumerate(ranges):filters.append(f'[0:v]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[t{n}]')
  filters.append(''.join(f'[t{n}]' for n in range(len(ranges)))+f'concat=n={len(ranges)}:v=1:a=0,fps=30,trim=end_frame=141,settb=1/30,setpts=N/(30*TB),format=yuv420p[v]')
  command(['ffmpeg','-v','error','-y','-i',str(source),'-filter_complex',';'.join(filters),'-map','[v]','-an','-c:v','libx264','-preset','fast','-crf','18',str(ACTION)])
 lines=[]
 for l in (BASE/'hetongzhoudu-mask/output/story.ass').read_text().splitlines():
  if l.startswith('Dialogue:'):
   p=l.split(',',9)
   if p[3] not in ['Header','Tag']:continue
   p[1]='0:00:00.00';p[2]=cards.tm((END-START)/30);p[9]=p[9].replace(r'{\fad(150,200)}','');l=','.join(p)
  lines.append(l)
 ass=OUT/'mask-action-header.ass';ass.write_text('\n'.join(lines)+'\n')
 ratio=((END-START)/30)/4.7
 f=[f'[0:v]trim=end_frame={START},setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p[a]',f"[1:v]trim=duration=4.7,setpts={ratio}*(PTS-STARTPTS),scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=0.1,trim=end_frame={END-START},ass=filename='{ass}':fontsdir='{cards.FONT}',settb=1/30,setpts=N/(30*TB),fps=30,format=yuv420p[b]",f'[0:v]trim=start_frame={END}:end_frame={TOTAL},setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p[c]','[a][b][c]concat=n=3:v=1:a=0,fps=30,settb=1/30,setpts=N/(30*TB),format=yuv420p[v]']
 # New action gets the same underlying song, plus brief restrained Foley, no dialogue.
 x=audio(SRC);music=audio(ROOT/'mask-music.wav');a=round(START/30*RATE);b=round(END/30*RATE);replacement=music[a:b]*1.6
 rng=np.random.default_rng(116)
 def fx(at,duration,kind,db,pan=0):
  t=np.arange(round(duration*RATE))/RATE
  if kind=='air':z=signal.sosfilt(signal.butter(2,[500,5500],btype='bandpass',fs=RATE,output='sos'),rng.normal(size=len(t)))*np.sin(np.pi*t/duration)**2
  elif kind=='metal':z=(np.sin(2*np.pi*2140*t)+.4*np.sin(2*np.pi*3169*t))*np.exp(-t*40)*np.minimum(t/.001,1)
  else:z=signal.sosfilt(signal.butter(2,[160,1800],btype='bandpass',fs=RATE,output='sos'),rng.normal(size=len(t)))*np.exp(-t*45)*np.minimum(t/.001,1)
  z=z/max(abs(z).max(),1e-8)*10**(db/20);n=round(at*RATE);k=min(len(z),len(replacement)-n)
  replacement[n:n+k]+=z[:k,None]*np.array([np.cos((pan+1)*np.pi/4),np.sin((pan+1)*np.pi/4)])
 # Cue positions can be adjusted after visual review of the generated shot.
 cues=json.loads((ROOT/'mask-foley-cues.json').read_text())
 for c in cues:fx(**c)
 n=round(.12*RATE);fade=np.linspace(0,1,n);replacement[:n]=x[a:a+n]*(1-fade[:,None])+replacement[:n]*fade[:,None];replacement[-n:]=replacement[-n:]*(1-fade[:,None])+x[b-n:b]*fade[:,None];x[a:b]=replacement
 wav=OUT/'mask-repaired-audio.wav';wavfile.write(wav,RATE,x.astype(np.float32))
 raw=OUT/'mask-repaired-base.mp4'
 command(['ffmpeg','-v','error','-y','-i',str(SRC),'-i',str(ACTION),'-i',str(wav),'-filter_complex_threads','1','-filter_complex',';'.join(f),'-map','[v]','-map','2:a','-c:v','libx264','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-r','30','-fps_mode','cfr','-enc_time_base:v','1:30','-video_track_timescale','30000','-c:a','aac','-b:a','256k','-ar','48000','-t',str(TOTAL/30),'-movflags','+faststart',str(raw)])
 cards.OUT=OUT;cards.CONFIG[3]['source']=str(raw);cards.CONFIG[3]['output']='04_面具之下_动作修订版.mp4';cards.render(4)
if __name__=='__main__':render()
