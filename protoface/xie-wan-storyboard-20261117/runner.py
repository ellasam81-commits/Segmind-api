import os,json,time,hashlib,math,base64
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-wan-storyboard-20261117');Q=json.loads((P/'request.json').read_text());key=os.environ['PROTOFACE_API_KEY'].strip()
a=httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180)
def call(m,p,**kw):
 r=a.request(m,p,**kw)
 if not r.is_success:raise RuntimeError(str(r.status_code)+' '+r.text[:500].replace(key,'[REDACTED]'))
 return r.json()
def run(job):
 mid='alibaba/wan-3.0';p=job['payload'].copy()
 p['reference_images']=['data:image/jpeg;base64,'+(P/job['board']).read_text().strip()]
 model=call('GET','/v1/models/'+mid);Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 cost=math.ceil(model['pricing']['qualities'][p['resolution']]['credits_per_second']*p['duration'])
 if cost>75:raise RuntimeError('Price exceeds 75 credit cap')
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 r=call('POST','/v1/run/'+mid,json=p,headers={'Idempotency-Key':'xie-wan60-v1-'+job['label']+'-'+digest});rid=r['id']
 print('ACCEPTED',job['label'],rid,'CREDITS',cost,flush=True)
 for _ in range(360):
  s=call('GET','/v1/runs/'+rid+'/status')
  if s['status'] in ['completed','failed','canceled']:break
  time.sleep(8)
 r=call('GET','/v1/runs/'+rid)
 if r['status']!='completed':raise RuntimeError('Run ended '+r['status'])
 outs=[x for x in r.get('outputs',[]) if x.get('modality')=='video'];obj=r.get('video') or outs[0]['file']
 aid=obj.get('asset_id') or obj.get('id') or outs[0].get('asset_id') or outs[0].get('id')
 print('MEDIA_RESULT '+json.dumps({'label':job['label'],'run_id':rid,'asset_id':aid,'credits':r.get('credits'),'file':obj}),flush=True)
balance=float(call('GET','/v1/billing/quota')['balance_credits']);print('BALANCE',balance,flush=True)
if balance < 75*len(Q['jobs']):raise RuntimeError('Insufficient balance for this batch')
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in [pool.submit(run,j) for j in Q['jobs']]:f.result()
