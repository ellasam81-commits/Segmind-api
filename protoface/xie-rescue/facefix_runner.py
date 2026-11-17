import os,json,time,math,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-rescue');Q={"scenes":[{"n":13,"prompt":"Animate this exact reference as a continuous five-second refined 2D anime closeup. Strictly preserve this man's exact narrow eyes, adult face shape, nose and lips, black high ponytail with ornate crown, and ornate silver swirling engraved plate armor with beast-head shoulders. Maintain high-detail painterly linework. Never replace armor with fish scales or simplify the face. No camera cut or new angle. He looks toward a woman offscreen on the boat, calm, quietly resolute. 0-1.1 seconds lips closed, subtle breath and tiny hair movement. 1.1-2.3 seconds he says in natural low male Mandarin voice: “他们还信我。” 2.3-2.8 seconds natural pause with mouth closed. 2.8-4.4 seconds he continues clearly: “我就还能救更多人。” 4.4-5 seconds mouth closed, resolute gaze. Precise restrained lip motion, slight facial acting, no large head movement. No other people in frame. Moonlit river bokeh remains unchanged. Quiet water and breeze, no music, no additional dialogue, no subtitles."}]};O=Path('output');O.mkdir(exist_ok=True)
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
 p={'operation':'video.animate','duration':5,'resolution':'480p','aspect_ratio':'9:16','enable_audio':True,'enable_prompt_expansion':False,'prompt':j['prompt'],'image':'data:image/jpeg;base64,'+(P/'facefix.b64').read_text().strip()}
 Draft202012Validator(model['request_schemas'][p['operation']]).validate(p)
 digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:24]
 with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=180) as c:
  r=call(c,'POST','/v1/run/alibaba/wan-3.0',json=p,headers={'Idempotency-Key':'xie-rescue-facefix-1117-'+label+'-'+digest})
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
