"""Wardrobe editing with fixed budgets, idempotency and no paid retries."""
import base64,hashlib,json,math,os,subprocess,sys,time
from pathlib import Path
import httpx
from threading import Lock
LOCK=Lock()
from jsonschema import Draft202012Validator
ROOT=Path('protoface/hetongzhoudu-episode05-20261116');OUT=Path('hetongzhoudu-episode05-output');OUT.mkdir(exist_ok=True)
REQ=json.loads((ROOT/'request.json').read_text())
KEY=os.environ['PROTOFACE_API_KEY'].strip();SPENT=0
API=httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+KEY},timeout=180)
def call(method,path,**kw):
 r=API.request(method,path,**kw)
 if not r.is_success:raise RuntimeError(f'Provider HTTP {r.status_code}: '+r.text[:500].replace(KEY,'[REDACTED]'))
 return r.json()
def model(mid):return call('GET','/v1/models/'+mid)
def download(obj,dest):
 with httpx.Client(follow_redirects=True,timeout=180) as media:
  r=media.get(obj['url']);r.raise_for_status();dest.write_bytes(r.content)
def output(result,modality):
 outputs=[x for x in result.get('outputs',[]) if x.get('modality')==modality]
 obj=result.get(modality) or outputs[0]['file'];aid=obj.get('asset_id') or obj.get('id') or outputs[0].get('asset_id') or outputs[0].get('id')
 return obj,aid
MOVES=[]
def run(mid,payload,label,cost):
 global SPENT
 m=model(mid);Draft202012Validator(m['request_schemas'][payload['operation']]).validate(payload)
 if m.get('available') is False:raise RuntimeError('Model unavailable')
 with LOCK:
  if SPENT+cost>REQ['budget_cap']:raise RuntimeError('Phase budget cap')
  SPENT+=cost
 if float(call('GET','/v1/billing/quota')['balance_credits'])<cost:raise RuntimeError('Insufficient remaining credits')
 digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]
 result=call('POST','/v1/run/'+mid,json=payload,headers={'Idempotency-Key':'episode05-20261116-'+label+'-'+digest})
 rid=result['id'];print('ACCEPTED',label,rid,'estimated_credits',cost,flush=True)
 for _ in range(300):
  s=call('GET','/v1/runs/'+rid+'/status')
  if s['status'] in ['completed','failed','canceled']:break
  time.sleep(8)
 result=call('GET','/v1/runs/'+rid);(OUT/(label+'-result.json')).write_text(json.dumps(result))
 if result['status']!='completed':raise RuntimeError('Generation '+label+' ended '+result['status'])
 mod='image' if payload['operation'].startswith('image.') else 'video';obj,aid=output(result,mod)
 download(obj,OUT/(label+('.png' if mod=='image' else '.mp4')))
 info={'label':label,'run_id':rid,'asset_id':aid,'credits':result.get('credits'),'file':obj};MOVES.append(info)
 print('MEDIA_RESULT '+json.dumps(info),flush=True);return aid


def main():
 m=model('openai/gpt-image-2')
 entry=next(x for x in m['pricing']['operations']['image.edit']['price_grid']['entries'] if x['quality']=='medium' and x['resolution']=='2k')
 cost=float(entry['credits'])
 if cost>10:raise RuntimeError('Reference price increased')
 ref=run(m['id'],{'operation':'image.edit','images':['asset_01M7GGWCSKSAJK7MQMTT0WFW9W'],'prompt':REQ['cast_prompt'],'quality':'medium','resolution':'2k','aspect_ratio':'9:16','output_format':'png'},'cast',cost)
 h=model('minimax/minimax-h3');jobs=[]
 for scene in REQ['scenes']:
  refs=[ref]
  if scene['n']==5:refs.append('asset_01M7GGTXAE2N710V4PWYK3BRK0')
  p={'operation':'video.general','reference':refs,'duration_seconds':scene['duration'],'quality':'768p','aspect_ratio':'9:16','generate_audio':True,'enhance_prompt':False,'prompt':REQ['common']+'\n'+scene['prompt']}
  Draft202012Validator(h['request_schemas']['video.general']).validate(p)
  rule=next(x for x in h['pricing']['add_ons'] if x['id']=='reference_image')['by_quality']['768p']
  price=math.ceil(scene['duration']*float(h['pricing']['qualities']['768p']['credits_per_second'])+max(0,len(refs)-int(rule.get('included',0)))*float(rule['credits_each']))
  jobs.append((h['id'],p,'scene-%02d'%scene['n'],price))
 if sum(j[3] for j in jobs)+SPENT>REQ['budget_cap']:raise RuntimeError('Full episode budget exceeded')
 from concurrent.futures import ThreadPoolExecutor
 with ThreadPoolExecutor(max_workers=3) as pool:
  futures=[pool.submit(run,*job) for job in jobs]
  for f in futures:f.result()
 (OUT/'results.json').write_text(json.dumps(MOVES))
 print('PHASE_COMPLETE episode05 estimated_credits',SPENT,flush=True)
if __name__=='__main__':
 try:main()
 except Exception as e:
  print('STOP',type(e).__name__,str(e).replace(KEY,'[REDACTED]')[:1200],flush=True);sys.exit(1)
