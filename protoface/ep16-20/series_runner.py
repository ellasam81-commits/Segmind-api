"""Native-audio episode factory with encrypted media transport and stable request IDs."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import base64
import hashlib
import io
import json
import os
import secrets
import subprocess
import sys
import time
import zipfile

import httpx
from jsonschema import Draft202012Validator,ValidationError

ROOT=Path(__file__).resolve().parent
TRANSPORT_ROOT=ROOT.parent/'ep01-c01'
if not TRANSPORT_ROOT.is_dir():TRANSPORT_ROOT=ROOT.parent/'thirteen-doors-ep01-c01'
sys.path.insert(0,str(TRANSPORT_ROOT))
import private_transport as transport

MODEL='minimax/minimax-h3'


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2));temp.replace(path)


def api(client,method,path,**kwargs):
    for attempt in range(4):
        response=client.request(method,path,**kwargs)
        if response.status_code in [502,503,504] and method=='GET' and attempt<3:
            time.sleep(3*(attempt+1));continue
        if not response.is_success:
            try:code=response.json().get('error',{}).get('code','provider_request_failed')
            except Exception:code='provider_request_failed'
            raise RuntimeError(f'Provider HTTP {response.status_code}: {code}')
        return response.json()


def estimated_part(model,packet=None):
    price=model['pricing'];value=5*price['qualities']['480p']['credits_per_second']
    rule=next(x for x in price['add_ons'] if x['id']=='reference_image')['by_quality']['480p']
    packet=packet or {}
    count=1
    value+=max(0,count-rule.get('included',0))*rule['credits_each']
    limit=packet.get('review_budget_credits',8)
    if limit>8 or value>limit:raise RuntimeError('Live price exceeds the reviewed per-part limit; no submission')
    return value


def payload(packet):
    if packet.get('extra_references') or any(packet.get(k) for k in ['first_frame','last_frame','reference_video','audio']):
        raise RuntimeError('The approved8-credit request uses exactly one three-panel reference image, no other media roles')
    body={'prompt':packet['prompt'],'reference':['data:image/jpeg;base64,'+x['data'] for x in [packet['image']]+packet.get('extra_references',[])],
            'duration_seconds':5,'quality':'480p','aspect_ratio':'16:9',
            'generate_audio':True,'enhance_prompt':bool(packet.get('enhance_prompt',False))}
    for name in ['first_frame','last_frame']:
        if packet.get(name):body[name]='data:image/jpeg;base64,'+packet[name]['data']
    return body


def init(episode,run_id,private_dir):
    repair_parts=os.environ.get('REVIEWED_REPAIR_PARTS','')
    repair=[int(x) for x in repair_parts.split(',')] if repair_parts else []
    if repair and (len(set(repair))!=len(repair) or any(x not in range(1,13) for x in repair)):raise ValueError('Invalid reviewed repair parts')
    public=ROOT/f'transport-public/ep{episode:02}'
    transport.init(private_dir,public,run_id)
    path=public/'ready.json';data=json.loads(path.read_text())
    data.update(episode=episode,parts=repair or list(range(1,13)));save(path,data)
    key=os.environ.get('PROTOFACE_API_KEY','').strip()
    if not key:raise RuntimeError('Provider secret is missing')
    with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=90) as client:
        model=api(client,'GET','/v1/models/'+MODEL)
        quota=api(client,'GET','/v1/billing/quota')
    price=estimated_part(model)
    required=len(repair) if repair else 12
    if quota.get('balance_credits',0)<required*price:raise RuntimeError('Balance does not cover the selected episode parts')
    if episode==16 and not repair and quota.get('balance_credits',0)<60*price:raise RuntimeError('Balance does not cover all five requested episodes')
    public=(TRANSPORT_ROOT/'return-public.pem').read_bytes()
    total=len(repair) if repair else 60
    envelope=transport.seal(json.dumps({'model':model,'quota':quota,'estimated_per_clip':price,'episode_count':1 if repair else 5,'clip_count':total,'estimated_batch_credits':total*price,'generation_submitted':False}).encode(),public,f'ep16-20-preflight-v1:{run_id}:ep{episode:02}')
    save(ROOT/f'transport-public/ep{episode:02}/preflight.sealed.json',envelope)
    print('Live five-second model price and funding checked; private figures encrypted.',flush=True)


def receive(episode,run_id,private_dir,repository):
    ready=json.loads((ROOT/f'transport-public/ep{episode:02}/ready.json').read_text())
    private=(private_dir/'input-private.pem').read_bytes()
    headers={'Accept':'application/vnd.github+json','User-Agent':'ThirteenDoors-private-episode-input'}
    if os.environ.get('GITHUB_TOKEN'):headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
    work=ROOT/f'work/ep{episode:02}';pending=set(ready['parts']);deadline=time.monotonic()+19200
    with httpx.Client(headers=headers,timeout=60,follow_redirects=False) as client:
        while pending and time.monotonic()<deadline:
            folder=f'protoface/ep16-20/private-inputs/{run_id}'
            listing=client.get(f'https://api.github.com/repos/{repository}/contents/{folder}',params={'ref':'main'})
            if listing.status_code==404:
                time.sleep(30);continue
            listing.raise_for_status()
            available={x['name'] for x in listing.json()}
            for part in sorted(pending):
                remote=f'protoface/ep16-20/private-inputs/{run_id}/ep-{episode:02}-part-{part:02}.enc.json'
                if remote.rsplit('/',1)[1] not in available:continue
                response=client.get(f'https://api.github.com/repos/{repository}/contents/{remote}',params={'ref':'main'})
                if response.status_code==404:continue
                response.raise_for_status();record=response.json()
                if record.get('encoding')!='base64':raise RuntimeError('Encrypted input is too large for inline transport')
                envelope=json.loads(base64.b64decode(record['content']))
                aad=f'ep16-20-native-v1:{run_id}:ep{episode:02}:part{part:02}:{ready["session_nonce"]}'
                plain=transport.unseal(envelope,private,aad)
                packet=json.loads(plain)
                if packet.get('episode')!=episode or packet.get('part')!=part:
                    raise RuntimeError('Private input identity mismatch')
                if 'speech_guide' in packet or 'audio' in packet:
                    raise RuntimeError('Post-dubbing and standalone audio references are disabled')
                transport.write_private(work/'packets'/f'part-{part:02}.json',plain)
                pending.remove(part);print('Private episode input received:',episode,part,flush=True)
            if pending:time.sleep(30)
    if pending:raise TimeoutError('Still missing some storyboard inputs; no paid request submitted')


def normalize(raw,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    command=['ffmpeg','-v','error','-y','-threads','2','-filter_threads','1','-i',str(raw),
        '-map','0:v:0','-map','0:a:0','-sn','-dn',
        '-vf','fps=24,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=0.3',
        '-t','5','-frames:v','120','-c:v','libx264','-preset','veryfast','-crf','18',
        '-threads','2','-pix_fmt','yuv420p','-af','apad=pad_dur=0.2,atrim=duration=5,asetpts=PTS-STARTPTS','-ar','32000','-ac','2','-c:a','aac','-b:a','192k','-movflags','+faststart',str(target)]
    done=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if done.returncode:raise RuntimeError('Native clip normalization failed; source is preserved in checkpoint')


def generate_one(episode,part,packet):
    work=ROOT/f'work/ep{episode:02}';state_path=work/'state'/f'part-{part:02}.json'
    raw=work/'raw'/f'part-{part:02}.mp4';target=work/'clips'/f'part-{part:02}.mp4'
    body=payload(packet)
    signature=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    request_key=f'thirteen-three5-v1-ep{episode:02}-p{part:02}-'+signature[:24]
    state=json.loads(state_path.read_text()) if state_path.exists() else {'idempotency_key':request_key,'input_sha256':signature}
    if state['idempotency_key']!=request_key:raise RuntimeError('Checkpoint input mismatch')
    key=os.environ['PROTOFACE_API_KEY']
    with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},
                      timeout=90,follow_redirects=False) as client:
        if not state.get('run_id'):
            if state.get('submission_uncertain'):raise RuntimeError('Submission outcome uncertain; recover same request instead of buying a replacement')
            for attempt in range(60):
                state['submission_uncertain']=True;save(state_path,state)
                response=client.post('/v1/run/'+MODEL,headers={'Idempotency-Key':request_key},json=body)
                if response.status_code==429:
                    state['submission_uncertain']=False;save(state_path,state);time.sleep(10);continue
                if not response.is_success:
                    state['submission_uncertain']=False
                    def safe_error(value):
                        if isinstance(value,dict):return {k:safe_error(v) for k,v in value.items() if k not in ['input','body','request','headers','authorization']}
                        if isinstance(value,list):return [safe_error(v) for v in value[:20]]
                        if isinstance(value,str):
                            if value.startswith('data:') or len(value)>1500:return '[large private value omitted]'
                            return value.replace(key,'[REDACTED]')
                        return value
                    try:state['submission_error']=safe_error(response.json())
                    except Exception:state['submission_error']={'status':response.status_code,'message':response.text[:800].replace(key,'[REDACTED]')}
                    save(state_path,state)
                    raise RuntimeError(f'Generation submission failed: HTTP {response.status_code}')
                created=response.json();state.update(run_id=created['id'],status=created['status'],
                    credit_estimate=created.get('credit_estimate'),submission_uncertain=False)
                save(state_path,state);print('Accepted native episode part:',episode,part,state['run_id'],flush=True);break
            else:raise RuntimeError('Concurrency remains full; no replacement request was created')
        deadline=time.monotonic()+2400;previous=None
        while time.monotonic()<deadline:
            status=api(client,'GET',f'/v1/runs/{state["run_id"]}/status')
            state['status']=status['status'];save(state_path,state)
            if state['status']!=previous:print('Episode part state:',episode,part,state['status'],flush=True);previous=state['status']
            if state['status'] in ['failed','canceled']:
                raise RuntimeError('Provider run ended without output; no automatic paid replacement')
            if state['status']=='completed':
                result=api(client,'GET',f'/v1/runs/{state["run_id"]}')
                state['credits']=result.get('credits');save(state_path,state)
                url=(result.get('video') or {}).get('url')
                if not url:url=next((x.get('file',{}).get('url') for x in result.get('outputs',[]) if x.get('modality')=='video'),None)
                if not url:raise RuntimeError('Completed run lacks a movie URL')
                parsed=httpx.URL(url)
                if parsed.scheme!='https' or parsed.userinfo:raise ValueError('Unexpected media URL')
                raw.parent.mkdir(parents=True,exist_ok=True)
                # A separate downloader never forwards the provider credential to asset hosts.
                with httpx.Client(timeout=120,follow_redirects=True) as downloader:
                    with downloader.stream('GET',url) as response:
                        response.raise_for_status()
                        with raw.open('wb') as f:
                            for chunk in response.iter_bytes():f.write(chunk)
                normalize(raw,target)
                return state
            time.sleep(5)
    raise TimeoutError('Provider run remains active; preserve its identity for recovery')


def generate(episode,selected_part=None):
    if os.environ.get('ALLOW_PAID_GENERATION')!='true':raise RuntimeError('Generation authorization is absent')
    key=os.environ.get('PROTOFACE_API_KEY','').strip()
    if not key:raise RuntimeError('Provider secret is missing')
    work=ROOT/f'work/ep{episode:02}'
    selected_parts=([selected_part] if isinstance(selected_part,int) else selected_part)
    numbers=selected_parts or list(range(1,13))
    packets={n:json.loads((work/'packets'/f'part-{n:02}.json').read_text()) for n in numbers}
    with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=90) as client:
        model=api(client,'GET','/v1/models/'+MODEL)
        if not model.get('available'):raise RuntimeError('H3 is currently unavailable')
        estimates={}
        for number,packet in packets.items():
            estimates[number]=estimated_part(model,packet)
            for media in [packet['image']]+packet.get('extra_references',[])+[packet[n] for n in ['first_frame','last_frame'] if packet.get(n)]:
                image=base64.b64decode(media['data'],validate=True)
                if hashlib.sha256(image).hexdigest()!=media['sha256']:raise RuntimeError('Image checksum mismatch')
            if len(packet['panels'])!=3:raise RuntimeError('Every input must have three panels')
            try:Draft202012Validator(model['request_schemas']['video.general']).validate(payload(packet))
            except ValidationError:raise RuntimeError('Private request schema validation failed; input was not logged') from None
            body=payload(packet)
            if any(body.get(x) for x in ['first_frame','last_frame']) and any(body.get(x) for x in ['reference','reference_video','audio']):
                raise RuntimeError('H3 frame roles cannot combine with reference roles; stopped before submission')
        quota=api(client,'GET','/v1/billing/quota')
        estimate=sum(estimates.values())
        if quota.get('balance_credits',0)<estimate:raise RuntimeError('Balance does not cover the selected parts; no submission')
    print('Episode inputs and current price validated:',episode,'estimated credits',estimate,flush=True)
    if selected_parts:
        states=[generate_one(episode,p,packets[p]) for p in selected_parts]
        save(work/'generation-report.json',{'episode':episode,'title':packets[selected_parts[0]]['title'],'parts':states,
          'tts_used':False,'post_dubbing':False,'reviewed_replacement_parts':selected_parts})
        print('Reviewed native replacement complete:',episode,selected_parts,flush=True)
        return
    with ThreadPoolExecutor(max_workers=1) as pool:
        futures=[pool.submit(generate_one,episode,n,packets[n]) for n in range(1,13)]
        states=[future.result() for future in futures]
    listing=work/'concat.txt';listing.write_text(''.join(f"file '{work/'clips'/f'part-{n:02}.mp4'}'\n" for n in range(1,13)))
    done=subprocess.run(['ffmpeg','-v','error','-y','-threads','2','-f','concat','-safe','0',
        '-i',str(listing),'-map','0:v:0','-map','0:a:0','-c:v','copy','-c:a','aac','-b:a','192k',
        '-t','60','-movflags','+faststart',str(work/'episode-native.mp4')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if done.returncode:raise RuntimeError('Native episode assembly failed; individual clips are preserved')
    save(work/'generation-report.json',{'episode':episode,'title':packets[1]['title'],'parts':states,
        'tts_used':False,'post_dubbing':False,'subtitles_and_corner_credits':'Applied locally after actual speech review.'})
    print('Native episode complete:',episode,flush=True)


def seal_results(episode,run_id):
    work=ROOT/f'work/ep{episode:02}';paths=[]
    for pattern in ['clips/*.mp4','state/*.json','episode-native.mp4','generation-report.json']:
        paths.extend(work.glob(pattern))
    for path in (work/'raw').glob('*.mp4'):
        if not (work/'clips'/path.name).exists():paths.append(path)
    if not paths:print('No provider checkpoint or generated media exists to export.');return
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
        for path in sorted(paths):z.write(path,f'ep{episode:02}/'+str(path.relative_to(work)))
    public=(TRANSPORT_ROOT/'return-public.pem').read_bytes()
    envelope=transport.seal(data.getvalue(),public,f'ep16-20-result-v1:{run_id}:ep{episode:02}')
    out=ROOT/'sealed-results';out.mkdir(exist_ok=True)
    save(out/f'ep{episode:02}.sealed.json',envelope)
    print('Episode output encrypted for local return:',episode,flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['init','receive','generate','seal'])
    p.add_argument('--episode',type=int,required=True,choices=range(16,21));p.add_argument('--run-id',type=int)
    p.add_argument('--private-dir',type=Path);p.add_argument('--repository')
    p.add_argument('--part',type=int,choices=list(range(1,13)))
    p.add_argument('--parts')
    a=p.parse_args()
    if a.mode=='init':init(a.episode,a.run_id,a.private_dir)
    elif a.mode=='receive':receive(a.episode,a.run_id,a.private_dir,a.repository)
    elif a.mode=='generate':
        selected=[int(x) for x in a.parts.split(',')] if a.parts else a.part
        if isinstance(selected,list) and (not selected or len(set(selected))!=len(selected) or any(x not in range(1,13) for x in selected)):
            raise ValueError('Invalid reviewed replacement selection')
        generate(a.episode,selected)
    else:seal_results(a.episode,a.run_id)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        # No request body, image data, private dialogue or credential is logged.
        print(str(exc).replace(os.environ.get('PROTOFACE_API_KEY') or '\x00','[REDACTED]'),flush=True)
        raise SystemExit(1)
