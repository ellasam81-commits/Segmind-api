import os,json,time,math,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-rescue');Q={'scenes':[{"n":5,"prompt":"10 second continuous 2D anime sword fight in this rainy narrow alley. Exactly TWO ADULT MEN in the entire scene: the referenced black-silver armored male hero and ONE MALE enemy soldier wearing a steel helmet, dark red tunic and red armband. No woman, no heroine, no orange hair, no dress, no civilians anywhere. The heroine has already left with refugees. Start from this exact male-only frame. Hero holds ONE straight sword in his RIGHT hand. Enemy approaches from screen right with ONE saber. 0-2s hero plants feet and turns toward the clearly visible male enemy. 2-4s enemy swings saber, hero blocks with his sword; both weapons meet visibly between the two men with small sparks. 4-6s hero steps outside enemy's guard, turns hips, pushes enemy's weapon away, then strikes ONLY the male enemy's breastplate with his sword hilt. 6-8s enemy stumbles backward while hero resets his stance. 8-10s hero retreats toward camera guarding the alley, enemy remains several steps behind. Readable fast grounded full-body choreography, no slow motion, precise sword contact and reaction, no wounds or gore. Maintain faces and clothes, no duplicates or morphing. Full-screen single scene, no montage, no text, no split-screen. Only rain, footstep, sword and cloth sounds, absolutely no speech or music."}]};O=Path('output');O.mkdir(exist_ok=True)
key=os.environ['PROTOFACE_API_KEY'].strip()
def call(c,m,p,**kw):
 r=c.request(m,p,**kw)
 if not r.is_success: raise RuntimeError('Provider HTTP '+str(r.status_code))
 return r.json()
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
 model=call(c,'GET','/v1/models/alibaba/wan-3.0')
 cost=math.ceil(float(model['pricing']['qualities']['480p']['credits_per_second'])*10)
 balance=float(call(c,'GET','/v1/billing/quota')['balance_credits'])
 if cost>50 or balance<cost*len(Q['scenes']): raise RuntimeError('Budget preflight failed')
 print('PREFLIGHT',len(Q['scenes']),cost*len(Q['scenes']),flush=True)
def run(j):
 label=f"{j['n']:02}"
 p={'operation':'video.animate','duration':10,'resolution':'480p','aspect_ratio':'9:16','enable_audio':True,'enable_prompt_expansion':False,'prompt':j['prompt'],'image':'data:image/jpeg;base64,'+(P/'combat-only.b64').read_text().strip()}
 Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xie-rescue-combat-only-1117-'+label+'-'+digest})
  rid=r['id'];(O/(label+'-accepted.json')).write_text(json.dumps(r))
  print('ACCEPTED',label,rid,flush=True)
  for _ in range(360):
   s=call(c,'GET','/v1/runs/'+rid+'/status')
   if s['status'] in ['completed','failed','canceled']: break
   time.sleep(8)
  r=call(c,'GET','/v1/runs/'+rid);(O/(label+'-result.json')).write_text(json.dumps(r))
  if r['status']!='completed':raise RuntimeError(label+' '+r['status'])
  outs=[x for x in r.get('outputs',[]) if x.get('modality')=='video'];obj=r.get('video') or outs[0]['file']
  with httpx.Client(timeout=180,follow_redirects=True) as d:
   b=d.get(obj['url']);b.raise_for_status();(O/(label+'.mp4')).write_bytes(b.content)
  print('COMPLETE',label,rid,flush=True)
errors=[]
with ThreadPoolExecutor(max_workers=3) as pool:
 for f in as_completed([pool.submit(run,j) for j in Q['scenes']]):
  try:f.result()
  except Exception as e:errors.append(str(e));print('ERROR',str(e).replace(key,'[REDACTED]'),flush=True)
if errors:raise SystemExit(1)
