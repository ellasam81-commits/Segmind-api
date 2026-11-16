"""Wardrobe editing with fixed budgets, idempotency and no paid retries."""
import base64,hashlib,json,math,os,subprocess,sys,time
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator
ROOT=Path('protoface/hetongzhoudu-clothes-20261116');OUT=Path('hetongzhoudu-clothes-output');OUT.mkdir(exist_ok=True)
REQ=json.loads((ROOT/'request.json').read_text());SOURCES=json.loads((ROOT/'source-index.json').read_text())
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
 if SPENT+cost>REQ['budget_cap']:raise RuntimeError('Phase budget cap')
 if float(call('GET','/v1/billing/quota')['balance_credits'])<cost:raise RuntimeError('Insufficient remaining credits')
 digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]
 result=call('POST','/v1/run/'+mid,json=payload,headers={'Idempotency-Key':'wardrobe-20261116-'+label+'-'+digest});SPENT+=cost
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

def original(project,label):
 result=call('GET','/v1/runs/'+SOURCES[project][label]['run_id']);obj,_=output(result,'video');dest=OUT/(project+'-'+label+'.mp4');download(obj,dest);return dest

def main():
 if REQ['phase']=='pilot':
  m=model('openai/gpt-image-2');entry=next(x for x in m['pricing']['operations']['image.edit']['price_grid']['entries'] if x['quality']=='medium' and x['resolution']=='2k');cost=float(entry['credits'])
  if cost>10:raise RuntimeError('Reference price changed')
  seated=run(m['id'],{'operation':'image.edit','images':['asset_01M7G7VZJ3Z66X1HPQP4P3ED8C'],'prompt':REQ['seated_prompt'],'quality':'medium','resolution':'2k','aspect_ratio':'9:16','output_format':'png'},'seated-clothed',cost)
  standing=run(m['id'],{'operation':'image.edit','images':['asset_01M7GDVA9S5D3GQGZCS69BWJNS',seated],'prompt':REQ['standing_prompt'],'quality':'medium','resolution':'2k','aspect_ratio':'9:16','output_format':'png'},'standing-clothed',cost)
  source=original('hetongzhoudu','scene-01');pilot=OUT/'pilot-input.mp4'
  subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-t','6','-an','-vf','fps=30','-c:v','libx264','-crf','18','-preset','fast',str(pilot)],check=True)
  m=model('pruna-ai/p-video-replace');grid=m['pricing']['operations']['video.edit']['price_grid']['entries'];price=next(x for x in grid if x['resolution']=='720p' and x['fps']=='original' and x['save_audio']==False and x['__input_count_images']==1)
  cost=math.ceil(float(price['unit_price_usd'])*6*100-1e-7)
  if cost>18:raise RuntimeError('Pilot price changed')
  run(m['id'],{'operation':'video.edit','images':[seated],'video':'data:video/mp4;base64,'+base64.b64encode(pilot.read_bytes()).decode(),'prompt':REQ['video_prompt'],'resolution':'720p','fps':'original','save_audio':False},'wardrobe-pilot',cost)
  h=model('minimax/minimax-h3');print('H3_SCHEMA '+json.dumps({'id':h['id'],'pricing':h['pricing'],'schema':h['request_schemas']}),flush=True)
 else:raise RuntimeError('Unknown phase')
 (OUT/'results.json').write_text(json.dumps(MOVES));print('PHASE_COMPLETE',REQ['phase'],'estimated_credits',SPENT,flush=True)
if __name__=='__main__':
 try:main()
 except Exception as e:
  print('STOP',type(e).__name__,str(e).replace(KEY,'[REDACTED]')[:1200],flush=True);sys.exit(1)
