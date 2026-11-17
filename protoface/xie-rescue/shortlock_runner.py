import os,json,time,math,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-rescue');Q={"scenes":[{"n":21,"duration":3,"ref":"waridentity.b64","prompt":"Animate the supplied illustration while preserving its EXACT finely painted face and elaborate engraved armor texture frame by frame. The narrow eye shape, nose, jaw, hair crown, hair strand detail, beast-head shoulders and curling silver breastplate engraving must remain identical to the input. Keep rich painterly shading, not simplified cel shading. One shot only, no angle changes, no cuts, no full body spin, no new characters, no dialogue, no text. Three-second side tracking mounted charge. Horse gallops fast with natural legs; hero remains in exactly the starting three-quarter angle and holds spear forward, hair and cloak streaming, mud splashes and high orange arrow trails. Keep hero's face large enough to identify, do not zoom out."},{"n":22,"duration":3,"ref":"shortwar.b64","prompt":"Animate the supplied illustration while preserving its EXACT finely painted face and elaborate engraved armor texture frame by frame. The narrow eye shape, nose, jaw, hair crown, hair strand detail, beast-head shoulders and curling silver breastplate engraving must remain identical to the input. Keep rich painterly shading, not simplified cel shading. One shot only, no angle changes, no cuts, no full body spin, no new characters, no dialogue, no text. Three-second tight mounted parry. The hero pushes the opposing spear away with one sharp outward movement of his own spear. Brief golden metal sparks scatter at contact. His head keeps almost the same angle with firm determined eyes; horse rocks beneath him, wind lifts a few hair strands. Static tracking closeup, no new faces."},{"n":23,"duration":2,"ref":"waridentity.b64","prompt":"Animate the supplied illustration while preserving its EXACT finely painted face and elaborate engraved armor texture frame by frame. The narrow eye shape, nose, jaw, hair crown, hair strand detail, beast-head shoulders and curling silver breastplate engraving must remain identical to the input. Keep rich painterly shading, not simplified cel shading. One shot only, no angle changes, no cuts, no full body spin, no new characters, no dialogue, no text. Two-second forward burst toward the gate. Horse accelerates to screen right, the hero leans slightly forward with spear lowered, splashing mud and far background siege impact throws orange sparks and dust. Same fixed side-tracking angle throughout, keep armor engraving detailed."},{"n":24,"duration":3,"ref":"identity14.b64","prompt":"Animate the supplied illustration while preserving its EXACT finely painted face and elaborate engraved armor texture frame by frame. The narrow eye shape, nose, jaw, hair crown, hair strand detail, beast-head shoulders and curling silver breastplate engraving must remain identical to the input. Keep rich painterly shading, not simplified cel shading. One shot only, no angle changes, no cuts, no full body spin, no new characters, no dialogue, no text. Three-second fast sword parry, two adult men only. Hero pushes the helmeted enemy's saber sideways with his straight sword, then steps half a pace forward. One clean weapon contact, bright brief sparks. Keep hero facing the same three-quarter angle toward camera, camera remains fixed. His face and engraved armor stay highly detailed."},{"n":25,"duration":4,"ref":"identity14.b64","prompt":"Animate the supplied illustration while preserving its EXACT finely painted face and elaborate engraved armor texture frame by frame. The narrow eye shape, nose, jaw, hair crown, hair strand detail, beast-head shoulders and curling silver breastplate engraving must remain identical to the input. Keep rich painterly shading, not simplified cel shading. One shot only, no angle changes, no cuts, no full body spin, no new characters, no dialogue, no text. Four seconds, fast grounded sword exchange. Enemy's saber slides off hero's sword; enemy cuts again from above, hero raises sword to parry once with sharp sparks, then shifts one step left to evade. NO rotation away from camera. Only two adult men, same framing, same detailed hero face throughout. Rain and metallic clashes."},{"n":26,"duration":3,"ref":"identity14.b64","prompt":"Animate the supplied illustration while preserving its EXACT finely painted face and elaborate engraved armor texture frame by frame. The narrow eye shape, nose, jaw, hair crown, hair strand detail, beast-head shoulders and curling silver breastplate engraving must remain identical to the input. Keep rich painterly shading, not simplified cel shading. One shot only, no angle changes, no cuts, no full body spin, no new characters, no dialogue, no text. Three-second decisive counter. Hero presses enemy saber outward with his sword, takes one short step and drives sword POMMEL into enemy chest armor, enemy recoils one step. Hero keeps his original face angle, stays upright, cloak snaps. No stabbing or injury. Two men only. Crisp armor impact sound."},{"n":27,"duration":3,"ref":"identity15.b64","prompt":"Animate the supplied illustration while preserving its EXACT finely painted face and elaborate engraved armor texture frame by frame. The narrow eye shape, nose, jaw, hair crown, hair strand detail, beast-head shoulders and curling silver breastplate engraving must remain identical to the input. Keep rich painterly shading, not simplified cel shading. One shot only, no angle changes, no cuts, no full body spin, no new characters, no dialogue, no text. Three-second dock defense. Hero quickly pushes enemy spear down and outward using his straight sword, follows with a firm forward step, enemy withdraws. Keep hero's face at exactly original three-quarter angle toward camera; no turning away, no view change. One clear contact and golden sparks. Two adult men only. Rain and metal sounds."}]};O=Path('output');O.mkdir(exist_ok=True)
key=os.environ['PROTOFACE_API_KEY'].strip()
def call(c,m,p,**kw):
 r=c.request(m,p,**kw)
 if not r.is_success: raise RuntimeError('Provider HTTP '+str(r.status_code))
 return r.json()
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
 model=call(c,'GET','/v1/models/alibaba/wan-3.0')
 cost=math.ceil(float(model['pricing']['qualities']['480p']['credits_per_second'])*21)
 balance=float(call(c,'GET','/v1/billing/quota')['balance_credits'])
 if cost>105 or balance<cost: raise RuntimeError('Budget preflight failed')
 print('PREFLIGHT',len(Q['scenes']),cost,flush=True)
def run(j):
 label=f"{j['n']:02}"
 p={'operation':'video.animate','duration':j['duration'],'resolution':'480p','aspect_ratio':'9:16','enable_audio':True,'enable_prompt_expansion':False,'prompt':j['prompt'],'image':'data:image/jpeg;base64,'+(P/j['ref']).read_text().strip()}
 Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xie-rescue-shortlock-1117-'+label+'-'+digest})
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
