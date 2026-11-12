"""Read-only recovery of exact previously paid EP51–60 runs. NEVER generate."""
from pathlib import Path
import base64,hashlib,json,os,time,urllib.request,urllib.error
from cryptography.hazmat.primitives import serialization,hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
ROOT=Path(__file__).resolve().parent
def seal(data):
 public=serialization.load_pem_public_key((ROOT/'return-public.pem').read_bytes())
 key=os.urandom(32);nonce=os.urandom(12);aad=b'thirteen-doors-existing-runs-recovery-v1'
 return {'aad':aad.decode(),'nonce':base64.b64encode(nonce).decode(),'wrapped_key':base64.b64encode(public.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))).decode(),'ciphertext':base64.b64encode(AESGCM(key).encrypt(nonce,data,aad)).decode()}
def main():
 request=json.loads((ROOT/'request.json').read_text());rows=request['runs'];raw=json.dumps(rows,sort_keys=True,separators=(',',':')).encode()
 assert request['operation']=='recover_existing_ep51_60_read_only' and request['maximum_new_generations']==0
 assert len(rows)==122 and len({r['provider_run_id']for r in rows})==122
 assert hashlib.sha256(raw).hexdigest()==request['runs_sha256']
 assert {(r['episode'],r['part'])for r in rows if not r['repair']}=={(e,n)for e in range(51,61)for n in range(1,13)}
 assert all(51<=r['episode']<=60 and 1<=r['part']<=12 for r in rows)
 allowed={r['provider_run_id']for r in rows};key=os.environ['PROTOFACE_API_KEY'].strip();result={'scope':'EP51–60 already accepted runs only','new_generations':0,'runs':[],'assets':[],'events':[],'errors':[]}
 def get(path):
  assert path.startswith('/v1/runs/')or path.startswith('/v1/assets?')
  if path.startswith('/v1/runs/'):assert path.split('/')[3].split('?')[0]in allowed
  url='https://api.protoface.com'+path
  for attempt in range(4):
   try:
    with urllib.request.urlopen(urllib.request.Request(url,headers={'Authorization':'Bearer '+key,'Accept':'application/json'},method='GET'),timeout=60)as response:return json.load(response)
   except urllib.error.HTTPError as exc:
    if exc.code in [429,502,503,504]and attempt<3:time.sleep(3);continue
    try:code=json.loads(exc.read()).get('error',{}).get('code','http_error')
    except Exception:code='http_error'
    return {'recovery_error':True,'http_status':exc.code,'code':code}
   except Exception as exc:return {'recovery_error':True,'class':type(exc).__name__}
  return {'recovery_error':True,'code':'exhausted_get'}
 try:
  for i,row in enumerate(rows):
   view=get('/v1/runs/'+row['provider_run_id']);result['runs'].append({'identity':row,'view':view})
   if (i+1)%12==0:print('Existing run records read:',i+1,flush=True)
   if view.get('http_status')in[401,403]:break
   time.sleep(.15)
  # Discover whether inline storyboard inputs remain as recoverable input assets.
  cursor=None
  for page in range(5):
   path='/v1/assets?limit=100'+('&starting_after='+cursor if cursor else '')
   listing=get(path)
   if listing.get('recovery_error'):result['errors'].append({'assets':listing});break
   data=listing.get('data',[]);result['assets'] += [x for x in data if '2026-11-11T18:00:00'<=x.get('created_at','')<='2026-11-11T23:10:00']
   if not data or not listing.get('has_more')or min(x.get('created_at','')for x in data)<'2026-11-11T18:00:00':break
   cursor=listing.get('next_cursor')
   if not cursor:break
  targets=[x for x in rows if(x['episode'],x['part'],x['repair'])in[(51,1,False),(60,9,False),(58,12,True)]]
  for row in targets:result['events'].append({'identity':row,'events':get('/v1/runs/'+row['provider_run_id']+'/events?limit=100')})
 finally:
  out=ROOT/'sealed';out.mkdir(exist_ok=True);(out/'probe.sealed.json').write_text(json.dumps(seal(json.dumps(result,ensure_ascii=False).encode())))
 print('Read-only recovery probe sealed; new generation requests:0',flush=True)
if __name__=='__main__':main()
