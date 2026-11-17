import os,json,time,math,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-rescue');Q={'scenes':[{"n":0,"prompt":"Animate this exact anime frame for five seconds. Ancient execution courtyard BEFORE punishment. Keep the seated white-robed adult male, loose black hair, intact body and FIVE stationary horses with guards. Ropes stay slack, no pulling or injuries. 0-2s wide establishing shot, slow drift of dust, flags flutter, horses breathe. 2-5s cinematic push toward his calm defiant face, loose hair moves in dawn wind. Female Mandarin voiceover says once clearly: “他们要车裂的，是谢却山。” No visible character moves lips. Restrained ominous wind and horse snort, no music, no other speech, no text. Single coherent full-screen 2D anime scene, no collage. No actual punishment, no blood."},{"n":9,"prompt":"Animate this exact anime frame for five seconds. Same white-robed adult prisoner seated intact, ropes slack, five horses and guards still waiting; dawn execution courtyard. 0-1s wide shot, a gust lifts dust. 1-3s an adult young woman calls from OFFSCREEN in clear urgent Mandarin once: “谢却山！等我！” The man turns his head toward that offscreen voice, mouth closed. 3-5s close-up his face as warm orange flame-light enters from screen right and reflects in his eyes, faint hope replaces resignation. Woman is approaching OFFSCREEN, do not show or invent her face. No one pulls the ropes; horses remain still. Wind, hoof shuffle, subtle flame sound. No music, no additional speech, no text, no collage. Beautiful cinematic 2D anime, no injuries or gore."}]};O=Path('output');O.mkdir(exist_ok=True)
key=os.environ['PROTOFACE_API_KEY'].strip()
def call(c,m,p,**kw):
 r=c.request(m,p,**kw)
 if not r.is_success: raise RuntimeError('Provider HTTP '+str(r.status_code))
 return r.json()
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
 model=call(c,'GET','/v1/models/alibaba/wan-3.0')
 cost=math.ceil(float(model['pricing']['qualities']['480p']['credits_per_second'])*5)
 balance=float(call(c,'GET','/v1/billing/quota')['balance_credits'])
 if cost>25 or balance<cost*len(Q['scenes']): raise RuntimeError('Budget preflight failed')
 print('PREFLIGHT',len(Q['scenes']),cost*len(Q['scenes']),flush=True)
def run(j):
 label=f"{j['n']:02}"
 p={'operation':'video.animate','duration':5,'resolution':'480p','aspect_ratio':'9:16','enable_audio':True,'enable_prompt_expansion':False,'prompt':j['prompt'],'image':'data:image/jpeg;base64,'+(P/'execution.b64').read_text().strip()}
 Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xie-rescue-execution-1117-'+label+'-'+digest})
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
