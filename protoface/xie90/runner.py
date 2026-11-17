import os,json,time,math,hashlib,sys,base64
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie90');Q=json.loads((P/sys.argv[1]).read_text());O=Path('output');O.mkdir(exist_ok=True)
key=os.environ['PROTOFACE_API_KEY'].strip()
def call(c,m,p,**kw):
 r=c.request(m,p,**kw)
 if not r.is_success:raise RuntimeError('HTTP '+str(r.status_code)+' '+r.text[:200].replace(key,'[REDACTED]'))
 return r.json()
def run(j):
 label=f"{j['id']:02}"
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  p=j['payload'].copy();p['reference_images']=['data:image/jpeg;base64,'+(P/'boards'/f'{label}.b64').read_text().strip()]
  m=call(c,'GET','/v1/models/alibaba/wan-3.0')
  Draft202012Validator(m['request_schemas'][p['operation']]).validate(p)
  cost=math.ceil(m['pricing']['qualities']['480p']['credits_per_second']*5)
  if cost>25:raise RuntimeError('Price changed; stop')
  digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xqs90-v1-'+label+'-'+digest})
  rid=r['id'];(O/(label+'-accepted.json')).write_text(json.dumps(r))
  print('ACCEPTED '+json.dumps({'id':j['id'],'run_id':rid}),flush=True)
  for _ in range(360):
   s=call(c,'GET','/v1/runs/'+rid+'/status')
   if s['status'] in ['completed','failed','canceled']:break
   time.sleep(8)
  r=call(c,'GET','/v1/runs/'+rid);(O/(label+'-result.json')).write_text(json.dumps(r))
  if r['status']!='completed':raise RuntimeError(label+' '+r['status'])
  outs=[x for x in r.get('outputs',[]) if x.get('modality')=='video'];obj=r.get('video') or outs[0]['file']
  print('MEDIA_RESULT '+json.dumps({'id':j['id'],'run_id':rid,'file':obj}),flush=True)
  with httpx.Client(timeout=180,follow_redirects=True) as d:
   b=d.get(obj['url']);b.raise_for_status();(O/(label+'.mp4')).write_bytes(b.content)
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=90) as c:
 if float(call(c,'GET','/v1/billing/quota')['balance_credits'])<25*len(Q['jobs']):raise RuntimeError('Insufficient credits')
errors=[]
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(run,j) for j in Q['jobs']]):
  try:f.result()
  except Exception as e:errors.append(str(e));print('SEGMENT_ERROR',str(e),flush=True)
if errors:raise SystemExit(1)
