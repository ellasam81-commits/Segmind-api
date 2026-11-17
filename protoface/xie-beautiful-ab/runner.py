import os,json,time,hashlib,math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-beautiful-ab');O=P/'output';O.mkdir(exist_ok=True)
Q=json.loads((P/'request.json').read_text());key=os.environ['PROTOFACE_API_KEY'].strip()
def call(c,m,p,**kw):
 r=c.request(m,p,**kw)
 if not r.is_success: raise RuntimeError('HTTP '+str(r.status_code)+' '+r.text[:300].replace(key,'[REDACTED]'))
 return r.json()
def run(j):
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  p=j['payload'].copy();p['reference_images']=['data:image/jpeg;base64,'+(P/'board.b64').read_text().strip()]
  model=call(c,'GET','/v1/models/'+j['model'])
  if not model.get('available'):raise RuntimeError('Model unavailable')
  Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
  cost=math.ceil(model['pricing']['qualities'][p['resolution']]['credits_per_second']*p['duration'])
  if cost>j['cap']:raise RuntimeError('Price exceeds cap')
  digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
  r=call(c,'POST','/v1/run/'+j['model'],json=p,headers={'Idempotency-Key':'xqs-beautiful-ab-v1-'+j['label']+'-'+digest})
  rid=r['id'];(O/(j['label']+'-accepted.json')).write_text(json.dumps(r))
  print('ACCEPTED '+json.dumps({'label':j['label'],'run_id':rid,'credits':cost}),flush=True)
  for _ in range(360):
   s=call(c,'GET','/v1/runs/'+rid+'/status')
   if s['status'] in ['completed','failed','canceled']:break
   time.sleep(8)
  r=call(c,'GET','/v1/runs/'+rid)
  (O/(j['label']+'-result.json')).write_text(json.dumps(r))
  if r['status']!='completed':raise RuntimeError(j['label']+' '+r['status']+'; no replacement submitted')
  outs=[x for x in r.get('outputs',[]) if x.get('modality')=='video'];obj=r.get('video') or outs[0]['file']
  print('MEDIA_RESULT '+json.dumps({'label':j['label'],'run_id':rid,'file':obj}),flush=True)
  with httpx.Client(timeout=180,follow_redirects=True) as download:
   media=download.get(obj['url']);media.raise_for_status();(O/(j['label']+'.mp4')).write_bytes(media.content)
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=90) as c:
 if float(call(c,'GET','/v1/billing/quota')['balance_credits'])<sum(j['cap'] for j in Q['jobs']):raise RuntimeError('Insufficient balance for both tests')
with ThreadPoolExecutor(max_workers=2) as pool:
 for f in [pool.submit(run,j) for j in Q['jobs']]:f.result()
