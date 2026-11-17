import os,json,time,math,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-rescue');Q={"scenes":[{"n":14,"duration":10,"prompt":"Animate this exact highly detailed 2D anime swordfight reference for ten seconds. Strictly keep the hero's exact mature face, narrow almond eyes, ornate crown, high black ponytail and elaborate black silver CURLING FILIGREE plate armor with beast-head shoulder guards. Never simplify the face or armor; no fish scale breastplate. Only TWO adult men, hero and helmeted red-armband enemy, no women. Fast grounded wuxia combat at full speed, no slow motion or freeze pose. 0-3s hero steps inward and redirects enemy saber with his sword, clear golden sparks on blade contact, pivots to evade return cut. 3-6s medium full-body side tracking: enemy attacks twice; hero blocks high then ducks low, wet footsteps splash, cape and ponytail whip. 6-8s hero takes one strong advancing step, presses enemy sword aside and strikes enemy chest ARMOR with sword pommel; enemy stumbles backward. 8-10s hero regains balanced guard and moves toward riverside alley exit; keep face recognizable. Brief crisp silver blade trails and gold contact sparks, realistic weight and clear separated weapons, no injury or blood. Elegant detailed cinematic anime rendering throughout. Rain, quick footfalls, sharp sword clashes and armor impact only; NO dialogue, no narration, no music, no subtitles."},{"n":15,"duration":3,"prompt":"Animate this exact refined 2D anime dock combat frame for THREE seconds. Maintain the same hero's exact narrow eyes, mature handsome face, ornate black silver engraved curling filigree breastplate, beast-head shoulders, crown and long high ponytail. Do not simplify character design. Two adult men only, no women. At full speed hero on right forcefully parries the helmeted enemy's spear DOWN and OUTWARD away from all bodies; small crisp golden sparks at weapon contact, he steps forward, turns his wrist and knocks the spear aside, enemy on left staggers back while hero holds the dock entrance. One coherent quick grounded parry-counter movement, visible weight transfer, rain splashes from boots, cape snaps. Detailed high-quality painterly anime, no slow motion, no cuts, no blood, no new characters, no text. Metallic clash, footfalls and rain only, NO voices or music."}]};O=Path('output');O.mkdir(exist_ok=True)
key=os.environ['PROTOFACE_API_KEY'].strip()
def call(c,m,p,**kw):
 r=c.request(m,p,**kw)
 if not r.is_success: raise RuntimeError('Provider HTTP '+str(r.status_code))
 return r.json()
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
 model=call(c,'GET','/v1/models/alibaba/wan-3.0')
 cost=math.ceil(float(model['pricing']['qualities']['480p']['credits_per_second'])*13)
 balance=float(call(c,'GET','/v1/billing/quota')['balance_credits'])
 if cost>65 or balance<cost: raise RuntimeError('Budget preflight failed')
 print('PREFLIGHT',len(Q['scenes']),cost,flush=True)
def run(j):
 label=f"{j['n']:02}"
 p={'operation':'video.animate','duration':j['duration'],'resolution':'480p','aspect_ratio':'9:16','enable_audio':True,'enable_prompt_expansion':False,'prompt':j['prompt'],'image':'data:image/jpeg;base64,'+(P/f"identity{j['n']}.b64").read_text().strip()}
 Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xie-rescue-combatidentity-1117-'+label+'-'+digest})
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
