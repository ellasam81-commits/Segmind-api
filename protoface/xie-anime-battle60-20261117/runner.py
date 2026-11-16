import os,json,time,hashlib,sys,math
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-anime-battle60-20261117');Q=json.loads((P/'request.json').read_text());key=os.environ['PROTOFACE_API_KEY'].strip()
a=httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=120)
def call(m,p,**kw):
 r=a.request(m,p,**kw)
 if not r.is_success:raise RuntimeError(str(r.status_code)+' '+r.text[:500].replace(key,'[REDACTED]'))
 return r.json()
def run(mid,p,label,cap):
 model=call('GET','/v1/models/'+mid);Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 if p['operation'].startswith('image'):
  cost=next(x['credits'] for x in model['pricing']['operations'][p['operation']]['price_grid']['entries'] if x['quality']==p['quality'] and x['resolution']==p['resolution'])
 else:cost=math.ceil(model['pricing']['qualities'][p['quality']]['credits_per_second']*p['duration_seconds'])
 if cost>cap:raise RuntimeError('Price exceeds per-job cap')
 if float(call('GET','/v1/billing/quota')['balance_credits'])<cost:raise RuntimeError('Insufficient credits')
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 r=call('POST','/v1/run/'+mid,json=p,headers={'Idempotency-Key':'xie-anime60-20261117-'+label+'-'+digest});rid=r['id'];print('ACCEPTED',label,rid,'CREDITS',cost,flush=True)
 for _ in range(300):
  s=call('GET','/v1/runs/'+rid+'/status')
  if s['status'] in ['completed','failed','canceled']:break
  time.sleep(8)
 r=call('GET','/v1/runs/'+rid)
 if r['status']!='completed':raise RuntimeError('Run ended '+r['status'])
 mod='image' if p['operation'].startswith('image') else 'video';outs=[x for x in r.get('outputs',[]) if x.get('modality')==mod];obj=r.get(mod) or outs[0]['file'];aid=obj.get('asset_id') or obj.get('id') or outs[0].get('asset_id') or outs[0].get('id')
 print('MEDIA_RESULT '+json.dumps({'label':label,'run_id':rid,'asset_id':aid,'credits':r.get('credits'),'file':obj}),flush=True)
if Q['phase']=='keyframe':run('openai/gpt-image-2',Q['payload'],'keyframe',10)
else:
 from concurrent.futures import ThreadPoolExecutor
 with ThreadPoolExecutor(max_workers=3) as pool:
  futures=[pool.submit(run,x['model'],x['payload'],x['label'],x['cap']) for x in Q['jobs']]
  for f in futures:f.result()
