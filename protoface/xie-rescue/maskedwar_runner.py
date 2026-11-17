import os,json,time,math,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-rescue');Q={"scenes":[{"n":30,"prompt":"Eight-second cinematic animated shot from this exact illustration. The hero MUST WEAR THE SAME ornate BLACK SILVER HALF-FACE WAR MASK for EVERY frame. Mask firmly covers brow, eyes surround and nose, lower mouth/jaw visible. Never remove, dissolve or change the mask. Preserve high black ponytail, ornate crown and black silver engraved breastplate and beast shoulders. 0-3s side tracking fast gallop toward city gate, horse legs cycle naturally, cloak streams, mud sprays, flaming arrows high overhead. 3-6s one helmeted enemy spear enters from right; mounted hero swiftly deflects it with his own long spear, sharp brief golden sparks at contact, enemy recoils. Keep hero masked and same detailed illustration style. 6-8s hero leads cavalry through the gap, distant siege impact raises dust beside city gate. No full rotation, no huge zoom-out, no shot cuts, keep readable masked face. Horse hoofbeats, rain, weapon clash, no dialogue or music, no captions, no women or civilians in combat, no gore."}]};O=Path('output');O.mkdir(exist_ok=True)
key=os.environ['PROTOFACE_API_KEY'].strip()
def call(c,m,p,**kw):
 r=c.request(m,p,**kw)
 if not r.is_success: raise RuntimeError('Provider HTTP '+str(r.status_code))
 return r.json()
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
 model=call(c,'GET','/v1/models/alibaba/wan-3.0')
 cost=math.ceil(float(model['pricing']['qualities']['480p']['credits_per_second'])*8)
 balance=float(call(c,'GET','/v1/billing/quota')['balance_credits'])
 if cost>40 or balance<cost*len(Q['scenes']): raise RuntimeError('Budget preflight failed')
 print('PREFLIGHT',len(Q['scenes']),cost*len(Q['scenes']),flush=True)
def run(j):
 label=f"{j['n']:02}"
 p={'operation':'video.animate','duration':8,'resolution':'480p','aspect_ratio':'9:16','enable_audio':True,'enable_prompt_expansion':False,'prompt':j['prompt'],'image':'data:image/jpeg;base64,'+(P/'maskedwar.b64').read_text().strip()}
 Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xie-rescue-maskedwar-1117-'+label+'-'+digest})
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
