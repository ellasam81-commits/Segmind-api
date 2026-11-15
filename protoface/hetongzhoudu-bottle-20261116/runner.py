"""Isolated fan video production; one submission per stable payload, no paid retries."""
import base64, hashlib, json, math, os, sys, time
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator

ROOT=Path('protoface/hetongzhoudu-bottle-20261116')
OUT=Path('hetongzhoudu-bottle-output'); OUT.mkdir(exist_ok=True)
REQ=json.loads((ROOT/'request.json').read_text())

def main():
    key=os.environ['PROTOFACE_API_KEY'].strip()
    if not key: raise RuntimeError('Missing repository secret')
    with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=90) as api:
        def call(method,path,**kwargs):
            response=api.request(method,path,**kwargs)
            if not response.is_success: raise RuntimeError(f'Provider HTTP {response.status_code}; no automatic replacement')
            return response.json()
        def run(model,payload,label,estimate):
            Draft202012Validator(model['request_schemas'][payload['operation']]).validate(payload)
            if model.get('available') is False: raise RuntimeError('Model unavailable')
            digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]
            result=call('POST','/v1/run/'+model['id'],json=payload,headers={'Idempotency-Key':'hetongzhoudu-bottle-20261116-'+label+'-'+digest})
            rid=result['id']
            (OUT/(label+'-submitted.json')).write_text(json.dumps(result))
            print('ACCEPTED',label,rid,'estimate',estimate,flush=True)
            for _ in range(180):
                status=call('GET','/v1/runs/'+rid+'/status')
                if status['status'] in ('completed','failed','canceled'): break
                time.sleep(8)
            else: raise RuntimeError('Polling timeout; resume existing request only')
            result=call('GET','/v1/runs/'+rid)
            (OUT/(label+'-result.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2))
            if result['status']!='completed': raise RuntimeError('Provider ended '+result['status'])
            modality='image' if payload['operation'].startswith('image.') else 'video'
            outputs=[x for x in result.get('outputs',[]) if x.get('modality')==modality]
            obj=result.get(modality) or outputs[0]['file']
            url=obj['url']
            with httpx.Client(follow_redirects=True,timeout=180) as media:
                response=media.get(url); response.raise_for_status()
            (OUT/(label+('.png' if modality=='image' else '.mp4'))).write_bytes(response.content)
            asset_id=obj.get('asset_id') or obj.get('id')
            if not asset_id and outputs: asset_id=outputs[0].get('asset_id') or outputs[0].get('id')
            print('MEDIA_RESULT '+json.dumps({'label':label,'url':url,'asset_id':asset_id,'credits':result.get('credits'),'file':obj},ensure_ascii=False),flush=True)
        balance=float(call('GET','/v1/billing/quota')['balance_credits'])
        if REQ['phase']=='cast':
            model=call('GET','/v1/models/openai/gpt-image-2')
            payload=dict(REQ['payload'])
            payload['images']=['data:image/jpeg;base64,'+(ROOT/'refs'/name).read_text().strip() for name in REQ['references']]
            entries=model['pricing']['operations']['image.edit']['price_grid']['entries']
            cost=float(next(x['credits'] for x in entries if x['quality']==payload['quality'] and x['resolution']==payload['resolution']))
            if cost>10 or balance<cost: raise RuntimeError('Reference budget cap reached')
            run(model,payload,'cast',cost)
        elif REQ['phase']=='video':
            model=call('GET','/v1/models/minimax/minimax-h3')
            payloads=[];costs=[]
            if len(REQ['scenes'])!=4: raise RuntimeError('Expected four scenes')
            for scene in REQ['scenes']:
                p={'operation':'video.general','prompt':REQ['common']+'\n'+scene['prompt'],'reference':[REQ['reference']],'duration_seconds':12,'quality':'480p','aspect_ratio':'9:16','generate_audio':True,'enhance_prompt':False}
                Draft202012Validator(model['request_schemas']['video.general']).validate(p)
                price=model['pricing'];rule=next(x for x in price['add_ons'] if x['id']=='reference_image')['by_quality']['480p']
                cost=math.ceil(12*float(price['qualities']['480p']['credits_per_second'])+max(0,1-int(rule.get('included',0)))*float(rule['credits_each']))
                payloads.append(p);costs.append(cost)
            if sum(costs)>60 or balance<sum(costs): raise RuntimeError('Video budget cap reached')
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=2) as pool:
                jobs=[pool.submit(run,model,p,f'scene-{i:02}',cost) for i,(p,cost) in enumerate(zip(payloads,costs),1)]
                for job in jobs: job.result()
        else: raise RuntimeError('Unknown phase')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        key=os.environ.get('PROTOFACE_API_KEY','')
        msg=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
        print('STOP',msg.replace(key,'[REDACTED]') if key else msg,flush=True)
        sys.exit(1)
