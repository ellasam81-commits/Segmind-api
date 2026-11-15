"""One authorized fan skit. Stable idempotency keys; no replacement generations."""
import hashlib
import json
import math
import os
import time
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator

ROOT = Path('protoface/hangbo-anime-20261115')
OUT = Path('hangbo-anime-output')
OUT.mkdir(exist_ok=True)
REQUEST = json.loads((ROOT / 'request.json').read_text())
IMAGE_MODEL = 'openai/gpt-image-2'
VIDEO_MODEL = 'minimax/minimax-h3'

def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2))

def main():
    key = os.environ.get('PROTOFACE_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Missing repository API key')
    with httpx.Client(base_url='https://api.protoface.com', headers={'Authorization': 'Bearer '+key}, timeout=90) as api:
        def call(method, path, **kwargs):
            r = api.request(method, path, **kwargs)
            if not r.is_success:
                raise RuntimeError(f'Provider HTTP {r.status_code}; no automatic replacement')
            return r.json()

        def run(model, payload, label, cost):
            schema = model['request_schemas'][payload['operation']]
            Draft202012Validator(schema).validate(payload)
            if model.get('available') is False:
                raise RuntimeError('Model unavailable')
            digest = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]
            idem = 'hangbo-anime-20261115-'+label+'-'+digest
            state = call('POST', '/v1/run/'+model['id'], json=payload, headers={'Idempotency-Key':idem})
            save(label+'-submitted.json',state)
            rid = state['id']
            print('ACCEPTED', label, rid, 'estimated_credits', cost, flush=True)
            for _ in range(180):
                status=call('GET','/v1/runs/'+rid+'/status')
                if status['status'] in ('completed','failed','canceled'):
                    break
                time.sleep(8)
            else:
                raise RuntimeError('Polling timed out; resume the same request only')
            result=call('GET','/v1/runs/'+rid)
            save(label+'-result.json',result)
            if result['status']!='completed':
                raise RuntimeError('Generation ended '+result['status'])
            modality='image' if payload['operation'].startswith('image.') else 'video'
            obj=result.get(modality) or next(x['file'] for x in result['outputs'] if x.get('modality')==modality)
            url=obj['url']
            with httpx.Client(follow_redirects=True,timeout=180) as media:
                response=media.get(url);response.raise_for_status()
            suffix='.png' if modality=='image' else '.mp4'
            (OUT/(label+suffix)).write_bytes(response.content)
            print('COMPLETED',label,'charged',result.get('credits',{}).get('charged'),flush=True)
            # Results remain in the workflow artifact; credentials are never logged.
            return result

        balance=float(call('GET','/v1/billing/quota')['balance_credits'])
        if REQUEST['phase']=='cast':
            model=call('GET','/v1/models/'+IMAGE_MODEL)
            payload=REQUEST['payload']
            prices=model['pricing']['operations'][payload['operation']]['price_grid']['entries']
            price=next(x for x in prices if x['quality']==payload['quality'] and x['resolution']==payload['resolution'])
            cost=float(price['credits'])
            if cost>22 or balance<cost:
                raise RuntimeError('Cast image exceeds 22-credit cap or available balance')
            run(model,payload,'cast',cost)
        elif REQUEST['phase']=='video':
            model=call('GET','/v1/models/'+VIDEO_MODEL)
            scenes=REQUEST['scenes']
            if len(scenes)!=3:
                raise RuntimeError('Exactly three reviewed video segments are required')
            payloads=[]
            costs=[]
            for scene in scenes:
                p={'operation':'video.general','prompt':REQUEST['common']+'\n'+scene['prompt'],
                   'reference':[REQUEST['reference']], 'duration_seconds':12,
                   'quality':'480p','aspect_ratio':'16:9','generate_audio':True,'enhance_prompt':False}
                Draft202012Validator(model['request_schemas']['video.general']).validate(p)
                rule=next(x for x in model['pricing']['add_ons'] if x['id']=='reference_image')['by_quality']['480p']
                cost=math.ceil(12*float(model['pricing']['qualities']['480p']['credits_per_second'])+
                               max(0,1-int(rule.get('included',0)))*float(rule['credits_each']))
                payloads.append(p);costs.append(cost)
            if sum(costs)>45 or balance<sum(costs):
                raise RuntimeError('Video total exceeds 45-credit cap or available balance')
            for i,(payload,cost) in enumerate(zip(payloads,costs),1):
                run(model,payload,f'scene-{i:02}',cost)
        else:
            raise RuntimeError('Unsupported production phase')

if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        key=os.environ.get('PROTOFACE_API_KEY','')
        message=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
        print('STOP',message.replace(key,'[REDACTED]') if key else message,flush=True)
        raise SystemExit(1)
