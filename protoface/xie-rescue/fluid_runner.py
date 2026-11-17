import os,json,time,math,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-rescue');Q={"scenes":[{"n":31,"duration":5,"ref":"identity14.b64","prompt":"Premium detailed Chinese anime martial arts animation, preserve EXACT face, black high ponytail, engraved black-silver armor and beast shoulder plates of the reference in EVERY frame. Full-speed grounded sword choreography, readable feet, weight shifts, hips drive shoulders then sword; blade contacts opponent weapon and opponent reacts immediately. No posing pauses, no reset to initial pose, no sliding feet, no teleporting weapons, no costume changes, no cuts or slow motion. Camera tracks gently at three-quarter full-body height, both fighters always visible. Brief sparks ONLY at metal contact, rain spray with steps, restrained pale blade trails, realistic inertia. One hero versus one helmeted enemy, no women. No dialogue or music; synced steel clashes, boots and cloth. Five seconds, a single flowing exchange starting from crossed blades: hero pushes opponent sword outward, takes a diagonal step to evade the enemy return slash, then counters with a compact horizontal slash against the enemy raised guard. Enemy stumbles back two steps; hero advances immediately and finishes balanced guard. Three connected actions, no stabbing or gore. Keep sword held in same right hand."},{"n":32,"duration":7,"ref":"identity14.b64","prompt":"Premium detailed Chinese anime martial arts animation, preserve EXACT face, black high ponytail, engraved black-silver armor and beast shoulder plates of the reference in EVERY frame. Full-speed grounded sword choreography, readable feet, weight shifts, hips drive shoulders then sword; blade contacts opponent weapon and opponent reacts immediately. No posing pauses, no reset to initial pose, no sliding feet, no teleporting weapons, no costume changes, no cuts or slow motion. Camera tracks gently at three-quarter full-body height, both fighters always visible. Brief sparks ONLY at metal contact, rain spray with steps, restrained pale blade trails, realistic inertia. One hero versus one helmeted enemy, no women. No dialogue or music; synced steel clashes, boots and cloth. Seven seconds, a continuous complete sword duel. 0-2s hero rolls his right wrist out of the initial blade bind and steps left while enemy chops diagonally; hero meets it with a rising parry. 2-4s hero advances with two fast precise cuts, enemy blocks first and retreats from second, clear contact and recovery. 4-6s enemy lunges, hero pivots one quarter turn and knocks enemy sword aside with his own blade. 6-7s hero shoulder-checks the opponent backward, opponent loses balance against wall, hero recovers stable ready stance. Crisp acceleration and follow-through, anatomically coherent connected actions. No full spinning, no bloody wounds."},{"n":33,"duration":3,"ref":"identity15.b64","prompt":"Premium detailed Chinese anime martial arts animation, preserve EXACT face, black high ponytail, engraved black-silver armor and beast shoulder plates of the reference in EVERY frame. Full-speed grounded sword choreography, readable feet, weight shifts, hips drive shoulders then sword; blade contacts opponent weapon and opponent reacts immediately. No posing pauses, no reset to initial pose, no sliding feet, no teleporting weapons, no costume changes, no cuts or slow motion. Camera tracks gently at three-quarter full-body height, both fighters always visible. Brief sparks ONLY at metal contact, rain spray with steps, restrained pale blade trails, realistic inertia. One hero versus one helmeted enemy, no women. No dialogue or music; synced steel clashes, boots and cloth. Three seconds at the dock: starting at the shown sword versus spear contact, hero drives spear tip down, steps inside its reach and forcefully pushes enemy backward with left palm against chest. Enemy visibly staggers back; hero finishes protecting the dock approach. One clean forceful action, continuous movement, do not end with a portrait zoom."}]};O=Path('output');O.mkdir(exist_ok=True)
key=os.environ['PROTOFACE_API_KEY'].strip()
def call(c,m,p,**kw):
 r=c.request(m,p,**kw)
 if not r.is_success: raise RuntimeError('Provider HTTP '+str(r.status_code))
 return r.json()
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
 model=call(c,'GET','/v1/models/alibaba/wan-3.0')
 cost=math.ceil(float(model['pricing']['qualities']['480p']['credits_per_second'])*15)
 balance=float(call(c,'GET','/v1/billing/quota')['balance_credits'])
 if cost>75 or balance<cost: raise RuntimeError('Budget preflight failed')
 print('PREFLIGHT',len(Q['scenes']),cost,flush=True)
def run(j):
 label=f"{j['n']:02}"
 p={'operation':'video.animate','duration':j['duration'],'resolution':'480p','aspect_ratio':'9:16','enable_audio':True,'enable_prompt_expansion':False,'prompt':j['prompt'],'image':'data:image/jpeg;base64,'+(P/j['ref']).read_text().strip()}
 Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xie-rescue-fluid-1117-'+label+'-'+digest})
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
