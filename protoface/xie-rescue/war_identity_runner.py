import os,json,time,math,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-rescue');Q={"scenes":[{"n":10,"prompt":"Animate this exact refined detailed 2D anime battlefield keyframe. STRICTLY preserve this exact adult face with narrow almond eyes and delicate hairline, ornate crown and high black ponytail, the elaborate BLACK PLATE armor with SILVER CURLING FILIGREE engraved chest and beast-head shoulders. Never change to fish-scale or geometric simplified breastplate, never simplify face into generic cartoon, keep rich fine linework throughout. Preserve the black horse. Eight seconds of fast readable cavalry combat. 0-3s low side-tracking shot: hero and cavalry gallop forcefully toward the fortified city gate, horses' legs cycle naturally, hooves kick sheets of muddy water, black banners whip. Flaming arrows streak high overhead. 3-6s a helmeted adult male enemy with red armband raises a spear beside the horse; hero forcefully sweeps his own spear to knock the enemy spear aside, a sharp brief shower of gold metal sparks at blade contact, enemy stumbles clear of the horse. 6-8s camera pulls wider as the hero leads cavalry through the opened gap, distant siege impact throws dust beside the gate. Fast full-speed action, strong weight and momentum, short crisp weapon arcs, no slow motion, no freeze frame. Sound of rapid galloping, rain, metallic clash and impact, no dialogue, no narration, no singing, no music. All combatants are adult armored men. No women, no civilians, no gore, no huge magical lasers. One coherent full-screen anime sequence, no text or panels."}]};O=Path('output');O.mkdir(exist_ok=True)
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
 p={'operation':'video.animate','duration':8,'resolution':'480p','aspect_ratio':'9:16','enable_audio':True,'enable_prompt_expansion':False,'prompt':j['prompt'],'image':'data:image/jpeg;base64,'+(P/'waridentity.b64').read_text().strip()}
 Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xie-rescue-waridentity-1117-'+label+'-'+digest})
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
