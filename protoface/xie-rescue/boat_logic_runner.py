import os,json,time,math,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-rescue');Q={"scenes":[{"n":11,"prompt":"Animate this exact anime frame for 13 seconds. Maintain exact identities and staging: flame-haired woman in red STAYS ON THE BOAT with two children and boatman, black silver armored general Xie Queshan STAYS ON THE DOCK. Never teleport the woman onto land. Clear natural Mandarin dialogue with precise lip sync; only speaking character moves lips. 0-1.5 seconds woman reaches toward him and calls: “谢却山，上船！” 1.5-5 seconds man answers firmly but gently: “你带他们走。我留下引开追兵。” 5-6.5 seconds woman asks anxiously: “那你怎么办？” 6.5-10.5 seconds man's closer shot, he says: “他们还信我，我就还能救更多人。” 10.5-13 seconds dialogue ends; wide shot, man turns away and walks alone along the dock toward the distant city gate while the boat begins drifting away with woman and children still aboard. Restrained emotion, clear rescue story, rain ripples, soft water and footsteps. No extra speech, no music, no captions, no fighting. Beautiful refined 2D anime, same black armor and long black ponytail throughout. No cuts to a new location."}]};O=Path('output');O.mkdir(exist_ok=True)
key=os.environ['PROTOFACE_API_KEY'].strip()
def call(c,m,p,**kw):
 r=c.request(m,p,**kw)
 if not r.is_success: raise RuntimeError('Provider HTTP '+str(r.status_code))
 return r.json()
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
 model=call(c,'GET','/v1/models/alibaba/wan-3.0')
 cost=math.ceil(float(model['pricing']['qualities']['480p']['credits_per_second'])*13)
 balance=float(call(c,'GET','/v1/billing/quota')['balance_credits'])
 if cost>65 or balance<cost*len(Q['scenes']): raise RuntimeError('Budget preflight failed')
 print('PREFLIGHT',len(Q['scenes']),cost*len(Q['scenes']),flush=True)
def run(j):
 label=f"{j['n']:02}"
 p={'operation':'video.animate','duration':13,'resolution':'480p','aspect_ratio':'9:16','enable_audio':True,'enable_prompt_expansion':False,'prompt':j['prompt'],'image':'data:image/jpeg;base64,'+(P/'boat-logic.b64').read_text().strip()}
 Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xie-rescue-boat-logic-1117-'+label+'-'+digest})
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
