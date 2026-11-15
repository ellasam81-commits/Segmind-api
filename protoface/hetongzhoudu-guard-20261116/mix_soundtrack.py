"""Mix the user-supplied song with dialogue ducking and original subtle Foley.

No generation/API charges. The supplied MP3 remains local and is not committed.
"""
from pathlib import Path
import json, math, subprocess
import numpy as np
from scipy import signal
from scipy.io import wavfile

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'; RATE=48000
TIMELINE=json.loads((ROOT/'wordart-timeline.json').read_text())
DURATION=TIMELINE['duration']; BODY=TIMELINE['body_duration']
SOURCE=OUT/'何不同舟渡_将军你不是受伤了吗_字幕版.mp4'
SONG=ROOT.parent/'upload/幻火.mp3'
DEST=OUT/'何不同舟渡_将军你不是受伤了吗_动漫二创.mp4'
N=round(DURATION*RATE); time=np.arange(N)/RATE
rng=np.random.default_rng(615)

def decode(path):
    raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-t',str(DURATION),'-ac','2','-ar',str(RATE),'-f','f32le','pipe:1'])
    x=np.frombuffer(raw,dtype=np.float32).reshape(-1,2)
    return np.pad(x[:N],((0,max(0,N-len(x))),(0,0)))
def ease(x):
    x=np.clip(x,0,1);return .5-.5*np.cos(np.pi*x)
def filtered(x,lo,hi):
    return signal.sosfilt(signal.butter(2,[lo,hi],btype='bandpass',fs=RATE,output='sos'),x)

voice=decode(SOURCE)
# Retain the spoken punchline; replace the old synthesized end-card chime.
voice*= (1-ease((time-BODY)/.08))[:,None]
music=decode(SONG)
music=signal.sosfilt(signal.butter(2,50,btype='highpass',fs=RATE,output='sos'),music,axis=0)
# Broad, modest presence dip leaves room for the Mandarin dialogue.
b,a=signal.iirpeak(2300,0.72,fs=RATE)
music-=.35*signal.lfilter(b,a,music,axis=0)

captions=json.loads((ROOT/'caption-timing.json').read_text())
offsets=json.loads((ROOT/'wordart-timeline.json').read_text())['scene_offsets']
speech=np.zeros(N); intervals=[]
for i in range(1,5):
    for a,b,_ in captions[str(i)]:
        a+=offsets[i-1];b+=offsets[i-1];intervals.append([a,b])
        window=ease((time-(a-.18))/.15)*(1-ease((time-(b+.03))/.38))
        speech=np.maximum(speech,window)
mid=music.mean(axis=1);side=(music[:,0]-music[:,1])*.5
mid*=1-.28*speech
music=np.stack([mid+side,mid-side],axis=1)

# Slow gain riding prevents loud sections of the supplied master taking over.
blocks=[];centers=[]
for start in range(0,N,RATE):
    blocks.append(np.sqrt(np.mean(music[start:start+RATE]**2)+1e-12))
    centers.append((start+RATE*.5)/RATE)
level=np.interp(time,centers,blocks)
outro=ease((time-(BODY+.05))/.45)
action=ease((time-(offsets[1]+.4))/.6)*(1-ease((time-(offsets[3]-.1))/.5))
target_db=(-26+4*action-7*speech)*(1-outro)+(-20)*outro
gain=np.clip(10**(target_db/20)/np.maximum(level,.03),.035,1.0)
gain*=ease(time/.9)*(1-ease((time-(DURATION-1.55))/1.55))
music*=gain[:,None]

music*=(1-.55*(ease((time-4.65)/.2)*(1-ease((time-6.3)/.35))))[:,None]
fx=np.zeros((N,2),dtype=np.float32);cues=[]
def place(name,start,x,peak_db=-29,pan=0):
    x=np.asarray(x,dtype=np.float32)
    x=x/max(float(np.max(np.abs(x))),1e-8)*10**(peak_db/20)
    left=math.cos((pan+1)*math.pi/4);right=math.sin((pan+1)*math.pi/4)
    at=round(start*RATE);size=min(len(x),N-at)
    fx[at:at+size]+=x[:size,None]*np.array([left,right])
    cues.append({'name':name,'time':start,'duration':round(len(x)/RATE,3),'peak_dbfs':peak_db})
def airy(duration):
    t=np.arange(round(duration*RATE))/RATE
    noise=filtered(rng.normal(size=len(t)),170,4300)
    return noise*np.sin(np.pi*t/duration)**1.6
def fire(duration):
    t=np.arange(round(duration*RATE))/RATE
    x=filtered(rng.normal(size=len(t)),90,2100)
    x*=np.sin(np.pi*t/duration)**1.8*(.75+.25*np.sin(2*np.pi*9*t))
    return x
def kettle(duration):
    n=round(duration*RATE);t=np.arange(n)/RATE
    steam=filtered(rng.normal(size=n),1900,6500)*.09
    bubbles=np.zeros(n)
    for _ in range(round(duration*27)):
        start=rng.integers(0,n-3000);d=rng.uniform(.035,.09)
        u=np.arange(round(d*RATE))/RATE
        f=rng.uniform(220,780)
        phase=2*np.pi*(f*u+f*4*u*u)
        wave=np.sin(phase)*np.exp(-u*55)*np.minimum(u/.003,1)*rng.uniform(.15,.7)
        stop=min(n,start+len(wave));bubbles[start:stop]+=wave[:stop-start]
    env=ease(t/.22)*(1-ease((t-(duration-.35))/.35))
    return (bubbles+steam)*env
def chime(duration,freq):
    t=np.arange(round(duration*RATE))/RATE
    return (np.sin(2*np.pi*freq*t)+.12*np.sin(2*np.pi*freq*2.01*t))*np.exp(-t/0.35)*np.minimum(t/.008,1)

def metal(duration):
    t=np.arange(round(duration*RATE))/RATE
    tone=sum(np.sin(2*np.pi*f*t)*np.exp(-t/tau) for f,tau in [(2100,.055),(2971,.04),(4247,.025)])
    return tone*np.minimum(t/.001,1)

# Foley timings follow the actual generated action.
for cue in json.loads((ROOT/'sfx-plan.json').read_text()):
    kind=cue['kind']; duration=cue['duration']
    sound=airy(duration) if kind=='air' else fire(duration) if kind=='fire' else metal(duration) if kind=='metal' else chime(duration,cue.get('frequency',698.456))
    place(cue['name'],cue['time'],sound,cue['peak_db'],cue.get('pan',0))
place('title soft air',BODY+.15,airy(.5),-32,0)
fx*=(1-.20*speech)[:,None]

mix=voice+music+fx
wav=OUT/'soundtrack-premaster.wav'
wavfile.write(wav,RATE,mix.astype(np.float32))
# Measure then use the same loudness values for a controlled two-pass master.
measure=subprocess.run(['ffmpeg','-hide_banner','-i',str(wav),'-af','loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
log=measure.stderr;stats=json.loads(log[log.rfind('{'):log.rfind('}')+1])
norm='loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:'+':'.join(f'{k}={stats[v]}' for k,v in [('measured_I','input_i'),('measured_TP','input_tp'),('measured_LRA','input_lra'),('measured_thresh','input_thresh'),('offset','target_offset')])
subprocess.run(['ffmpeg','-y','-v','error','-i',str(SOURCE),'-i',str(wav),'-map','0:v:0','-map','1:a:0','-c:v','copy','-af',norm,'-ar',str(RATE),'-c:a','aac','-b:a','256k','-t',str(DURATION),'-movflags','+faststart',str(DEST)],check=True)
report={'song':'幻火','source_range':[0,DURATION],'speech_duck_dbfs':-33,'gap_music_dbfs':-26,'action_music_dbfs':-22,'outro_music_dbfs':-20,'dialogue_intervals':intervals,'effects':cues,'loudness_measurement':stats,'video_reencoded':False,'duration':DURATION}
(ROOT/'audio-mix.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps({'output':str(DEST),'premaster_loudness':stats},ensure_ascii=False))
