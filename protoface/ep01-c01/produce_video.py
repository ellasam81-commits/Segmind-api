"""Generate four C01 shots; synthesize private speech guides; export exact dialogue."""
from __future__ import annotations
import argparse
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path
import ssl
import subprocess
import time
import wave

import httpx
from jsonschema import Draft202012Validator
import numpy as np

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
PRIVATE=ROOT/'private'
STATE=ROOT/'checkpoint'
RATE=48000
MODEL='minimax/minimax-h3'
SCRIPT={1:['青槐里十三号。'],2:['系统查不到，旧地图被涂改……','越被抹除的东西，往往离真相越近。'],
        3:['就是这儿？','青槐里十三号。'],4:['沈照夜，冷静。','空楼……哪来的敲门声？','头顶？']}
KNOCKS=[46.3,47.5,48.2,54.7,55.3,56.0]


def run(args):
    p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-1800:])


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2));temporary.replace(path)


def read_packet(number,folder='packed'):
    d=json.loads((ROOT/folder/f'part-{number:02}.json').read_text())
    if 'speech_guide' in d:raise ValueError('Raw speech guides must not be stored in public inputs')
    image=base64.b64decode(d['image']['data'],validate=True)
    if hashlib.sha256(image).hexdigest()!=d['image']['sha256']:raise ValueError('Storyboard checksum mismatch')
    if [q['text'] for q in d['dialogue']]!=SCRIPT[number]:raise ValueError('Dialogue differs from approved storyboard')
    panels=d['panels']
    if len(panels)!=9 or panels[0]['start']!=0 or panels[-1]['end']!=15:raise ValueError('Nine full-screen storyboard panels required')
    if any(a['end']!=b['start'] for a,b in zip(panels,panels[1:])):raise ValueError('Storyboard timing has a gap')
    return d


def pcm(path):
    return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-threads','2','-i',str(path),'-ar',str(RATE),'-ac','1','-f','f32le','pipe:1']),dtype='<f4').copy()


def write_wav(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    if data.ndim==1:data=np.column_stack([data,data])
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(RATE)
        f.writeframes((np.clip(data,-.97,.97)*32767).astype('<i2').tobytes())


def add(track,start,data,gain=1):
    at=round(start*RATE);end=min(len(track),at+len(data))
    track[at:end]+=data[:end-at]*gain


async def build_guide(number,packet):
    import edge_tts
    import edge_tts.communicate
    edge_tts.communicate._SSL_CTX=ssl.create_default_context(cafile='/etc/ssl/certs/ca-certificates.crt')
    PRIVATE.mkdir(parents=True,exist_ok=True)
    speech=np.zeros(15*RATE)
    for index,cue in enumerate(packet['dialogue'],1):
        raw=PRIVATE/f'raw-{number:02}-{index:02}.mp3'
        if not raw.exists() or raw.stat().st_size<1000:
            voice=edge_tts.Communicate(cue['text'],'zh-CN-YunxiNeural',rate='+10%' if cue['text']=='沈照夜，冷静。' else '-5%',pitch='-4Hz',
                proxy=os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy'))
            await voice.save(str(raw))
        data=pcm(raw);active=np.flatnonzero(np.abs(data)>.003)
        if not len(active):raise ValueError('Silent dialogue line')
        data=data[max(0,active[0]-round(.09*RATE)):min(len(data),active[-1]+round(.18*RATE))]
        allowed=cue['end']-cue['start']
        if cue['text']=='沈照夜，冷静。' and len(data)/RATE>allowed:
            ratio=len(data)/RATE/(allowed-.03)
            if ratio>1.3:raise ValueError('Name reminder needs pacing correction before generation')
            p=subprocess.run(['ffmpeg','-v','error','-f','f32le','-ar',str(RATE),'-ac','1','-i','pipe:0','-af',f'atempo={ratio:.6f}','-f','f32le','pipe:1'],
                input=data.astype('<f4').tobytes(),stdout=subprocess.PIPE,check=True)
            data=np.frombuffer(p.stdout,dtype='<f4').copy()
        if len(data)/RATE>allowed+.12:raise ValueError('Dialogue is too long for its storyboard slot')
        rms=float(np.sqrt(np.mean(data*data)));data*=min(.14/max(rms,1e-6),.82/max(float(np.max(np.abs(data))),1e-6))
        fade=min(240,len(data)//4);data[:fade]*=np.linspace(0,1,fade);data[-fade:]*=np.linspace(1,0,fade)
        add(speech,cue['start'],data)
    wav=PRIVATE/f'guide-{number:02}.wav';mp3=PRIVATE/f'guide-{number:02}.mp3'
    write_wav(wav,speech[:round(14.8*RATE)])
    run(['ffmpeg','-v','error','-y','-i',str(wav),'-t','14.8','-ac','1','-ar','24000','-c:a','libmp3lame','-b:a','96k',str(mp3)])
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(mp3)]))
    if float(info['format']['duration'])>=15:raise ValueError('Reference audio exceeds 15-second limit')
    return mp3,speech


def payload(packet,guide_bytes=b'validation-placeholder'):
    body={'prompt':packet['prompt'],'reference':['data:image/jpeg;base64,'+packet['image']['data']],
        'duration_seconds':15,'quality':'480p','aspect_ratio':'16:9','generate_audio':True,'enhance_prompt':False}
    if guide_bytes is not None:body['audio']=['data:audio/mpeg;base64,'+base64.b64encode(guide_bytes).decode()]
    return body


def api(client,method,path,**kwargs):
    r=client.request(method,path,**kwargs)
    if not r.is_success:
        try:e=r.json().get('error',{});message=str(e.get('code','request_failed'))+': '+str(e.get('message',''))
        except Exception:message='request_failed'
        raise RuntimeError(f'Protoface HTTP {r.status_code}: {message}')
    return r.json()


def price(model,include_audio=True):
    p=model['pricing'];total=15*p['qualities']['480p']['credits_per_second']
    for name in ['reference_image']+(['reference_audio'] if include_audio else []):
        rule=next(x for x in p['add_ons'] if x['id']==name)['by_quality']['480p']
        total+=max(0,1-rule.get('included',0))*rule['credits_each']
    if total>(21 if include_audio else 18):raise RuntimeError('Live price exceeds the disclosed estimate; no generation submitted')
    return total


def inspect(path,seconds):
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(path)]))
    video=next((s for s in info['streams'] if s['codec_type']=='video'),None)
    if not video or abs(video['width']-video['height']*16/9)>64:raise ValueError('Video is not widescreen')
    if abs(float(info['format']['duration'])-seconds)>.3:raise ValueError('Unexpected video duration')
    return info


def download_video(url,target):
    parsed=httpx.URL(url)
    if parsed.scheme!='https' or not parsed.host or parsed.userinfo:raise ValueError('Invalid media URL')
    temporary=target.with_suffix('.part')
    # Media hosts never receive the provider's API key.
    with httpx.Client(timeout=120,follow_redirects=True) as downloader:
        with downloader.stream('GET',url) as r:
            r.raise_for_status()
            with temporary.open('wb') as f:
                for chunk in r.iter_bytes():f.write(chunk)
    inspect(temporary,15);temporary.replace(target)


def generate(number,packet,guide):
    key=os.environ.get('PROTOFACE_API_KEY','').strip()
    if os.environ.get('ALLOW_PAID_GENERATION')!='true' or not key:raise RuntimeError('Generation authorization or credential missing')
    STATE.mkdir(exist_ok=True)
    signature=hashlib.sha256(json.dumps(packet,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    request_key=f'ep01-c01-exact-v1-{number}-'+signature[:24]
    record=STATE/f'part-{number:02}.json';native=STATE/f'native-{number:02}.mp4'
    state=json.loads(record.read_text()) if record.exists() else {'idempotency_key':request_key,'input_sha256':signature}
    if state['idempotency_key']!=request_key:raise ValueError('Checkpoint belongs to different inputs')
    if state.get('status')=='completed' and native.exists():inspect(native,15);return native
    with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=90,follow_redirects=False) as client:
        model=api(client,'GET','/v1/models/'+MODEL)
        if not model.get('available'):raise RuntimeError('MiniMax H3 unavailable')
        body=payload(packet,guide.read_bytes() if guide else None);Draft202012Validator(model['request_schemas']['video.general']).validate(body)
        expected=price(model,include_audio=guide is not None)
        if not state.get('run_id'):
            if state.get('submission_uncertain'):raise RuntimeError('Prior submission was uncertain; inspect that request instead of creating another')
            quota=api(client,'GET','/v1/billing/quota')
            if quota.get('balance_credits',0)<expected:raise RuntimeError('Balance cannot cover this 21-credit part')
            state['submission_uncertain']=True;save(record,state)
            created=api(client,'POST','/v1/run/'+MODEL,headers={'Idempotency-Key':request_key},json=body)
            state.update(run_id=created['id'],status=created['status'],credit_estimate=created.get('credit_estimate'),submission_uncertain=False)
            save(record,state);print('Accepted part',number,state['run_id'],'estimate',state['credit_estimate'],flush=True)
        deadline=time.monotonic()+2400;previous=None
        while time.monotonic()<deadline:
            status=api(client,'GET',f"/v1/runs/{state['run_id']}/status")
            state['status']=status['status'];save(record,state)
            if state['status']!=previous:print('Part',number,state['status'],flush=True);previous=state['status']
            if state['status'] in {'failed','canceled'}:raise RuntimeError('Accepted generation '+state['status']+'; no automatic replacement')
            if state['status']=='completed':
                result=api(client,'GET',f"/v1/runs/{state['run_id']}")
                url=(result.get('video') or {}).get('url')
                if not url:url=next((v.get('file',{}).get('url') for v in result.get('outputs',[]) if v.get('modality')=='video'),None)
                if not url:raise RuntimeError('Completed part has no video')
                download_video(url,native);state['credits']=result.get('credits');save(record,state);return native
            time.sleep(5)
    raise TimeoutError('Accepted provider run is still processing; preserve its identity')



def build_effects():
    manifest={"knocks":KNOCKS}
    rng = np.random.default_rng(1301)
    timeline = np.zeros(60*RATE)

    def noise(duration, gain=.01, decay=0, grain=1):
        count = round(duration*RATE)
        if grain > 1:
            positions = np.arange(0, count+grain, grain)
            data = np.interp(np.arange(count), positions, rng.normal(0, 1, len(positions)))
        else:
            data = rng.normal(0, 1, count)
        data *= gain
        if decay:
            data *= np.exp(-np.arange(count)/RATE*decay)
        edge = min(round(.02*RATE), count//4)
        data[:edge] *= np.linspace(0, 1, edge)
        data[-edge:] *= np.linspace(1, 0, edge)
        return data

    # Quiet office air, then exterior wind, then hollow interior air.
    add(timeline, 0, noise(26.5, .0015, grain=55))
    add(timeline, 26.5, noise(17, .005, grain=200))
    add(timeline, 43.5, noise(16.5, .003, grain=120))
    # Paper / envelope / map, only on the existing actions.
    for start, duration in [(1.7,.45),(3.2,.35),(4.0,.3),(11.4,.7),(13.1,.9),
                            (15.1,.4),(20.0,.7)]:
        add(timeline, start, noise(duration, .013, grain=3))
    for start in [7.8,8.0,8.22,8.5,8.71,8.95,9.1]:
        add(timeline, start, noise(.045, .018, decay=65, grain=2))

    # Ordinary key / zip / latch. High-frequency ticks cannot be mistaken for knocks.
    for start, gain in [(24.7,.025),(34.7,.075),(39.2,.015)]:
        t=np.arange(round(.20*RATE))/RATE
        data=gain*(np.sin(2*np.pi*1850*t)+.35*np.sin(2*np.pi*2840*t))*np.exp(-t*36)
        add(timeline,start,data)
    add(timeline,39.3,noise(.32,.016,grain=3))
    # Long iron hinge and cold draft as the gate opens; no extra impact.
    t=np.arange(round(1.65*RATE))/RATE
    hinge=.014*np.sin(2*np.pi*(260*t+30*t*t))*np.sin(np.pi*t/1.65)**2
    add(timeline,36.1,hinge+noise(1.65,.008,grain=6))
    add(timeline,36.3,noise(2.0,.018,grain=160))
    # Soft shoe scuffs (different timbre from the plot's distinct six knocks).
    for start in [25.4,25.9,41.3,41.9,42.5,43.1,43.8,44.5,45.1]:
        add(timeline,start,noise(.16,.021,decay=15,grain=18))
    for i, start in enumerate(manifest['knocks']):
        t=np.arange(round(.72*RATE))/RATE
        hit=(.30 if i<3 else .39)*(np.sin(2*np.pi*90*t)+.32*np.sin(2*np.pi*177*t))*np.exp(-t*13)
        hit*=np.minimum(t/.004,1)
        add(timeline,start,hit)
        add(timeline,start+.11,hit*.18)
        add(timeline,start+.24,hit*.065)
    write_wav(PRIVATE/'scripted-effects.wav',timeline)
    return timeline

def finalize_part(number,native,speech):
    effects=build_effects();offset=(number-1)*15
    mix=speech+effects[round(offset*RATE):round((offset+15)*RATE)]
    audio=PRIVATE/f'part-{number:02}-mix.wav';write_wav(audio,mix)
    destination=OUT/f'C01_EP01_part-{number:02}_480p.mp4'
    run(['ffmpeg','-v','error','-y','-threads','2','-filter_threads','1','-i',str(native),'-i',str(audio),
        '-map','0:v:0','-map','1:a:0','-sn','-dn','-vf','fps=24,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=0.3',
        '-t','15','-frames:v','360','-c:v','libx264','-preset','veryfast','-crf','19','-threads','2','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','192k','-movflags','+faststart',str(destination)])
    inspect(destination,15)
    return destination


def assemble(folder):
    files=[folder/f'C01_EP01_part-{n:02}_480p.mp4' for n in range(1,5)]
    for p in files:inspect(p,15)
    listing=OUT/'concat.txt';listing.write_text(''.join("file '"+str(p.resolve())+"'\n" for p in files))
    target=OUT/'C01_EP01_480p_60s.mp4'
    run(['ffmpeg','-v','error','-y','-threads','2','-filter_threads','1','-f','concat','-safe','0','-i',str(listing),
        '-map','0:v:0','-map','0:a:0','-sn','-dn','-vf','fps=24,setsar=1','-t','60','-c:v','libx264','-preset','veryfast','-crf','19','-threads','2','-pix_fmt','yuv420p',
        '-c:a','aac','-b:a','192k','-metadata','title=十三扇门 第1集 被抹除的地址，三声敲门','-metadata','artist=林爱丽','-movflags','+faststart',str(target)])
    inspect(target,60)
    save(OUT/'production-review.json',{'duration_seconds':60,'parts':4,'resolution':'854x480','dialogue':SCRIPT,
        'native_audio_discarded':True,'music':False,'subtitle_overlay':False,'knock_times':KNOCKS,
        'visual_review':'Review generated pictures against all 36 panels before claiming complete fidelity.',
        'lip_sync':'Timed speech guides supplied; frame-accurate lip sync requires visual review.'})


def main():
    global OUT,STATE
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['check','generate','assemble','native']);p.add_argument('--part',type=int,choices=range(1,5));p.add_argument('--inputs',default='packed');p.add_argument('--schema',type=Path);p.add_argument('--collected',type=Path);p.add_argument('--prompt',type=Path)
    a=p.parse_args();OUT.mkdir(exist_ok=True);PRIVATE.mkdir(exist_ok=True)
    if a.mode=='check':
        model=json.loads(a.schema.read_text());price(model)
        for n in range(1,5):Draft202012Validator(model['request_schemas']['video.general']).validate(payload(read_packet(n,a.inputs)))
        print('Validated four single-board inputs, eight exact lines, 15 seconds per part; raw audio is not public.');return
    if a.mode=='assemble':assemble(a.collected);return
    if not a.part:raise ValueError('Choose one part')
    packet=read_packet(a.part,a.inputs)
    if a.mode=='native':
        if not a.prompt:raise ValueError('Native trial requires the user prompt')
        OUT=ROOT/'native-user-prompt';STATE=ROOT/'checkpoint-user-prompt';OUT.mkdir(exist_ok=True);STATE.mkdir(exist_ok=True)
        packet['prompt']=a.prompt.read_text();packet['trial']='user-prompt-native-v1'
        native=generate(a.part,packet,None)
        destination=OUT/f'C01_EP01_part-{a.part:02}_USERPROMPT_480p.mp4'
        run(['ffmpeg','-v','error','-y','-threads','2','-filter_threads','1','-i',str(native),'-map','0:v:0','-map','0:a:0','-sn','-dn',
            '-vf','fps=24,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1',
            '-t','15','-c:v','libx264','-preset','veryfast','-crf','19','-threads','2','-c:a','aac','-b:a','192k','-movflags','+faststart',str(destination)])
        inspect(destination,15);return
    guide,speech=asyncio.run(build_guide(a.part,packet))
    native=generate(a.part,packet,guide)
    finalize_part(a.part,native,speech)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc).replace(os.environ.get('PROTOFACE_API_KEY') or '\x00','[REDACTED]'),flush=True);raise SystemExit(1)
