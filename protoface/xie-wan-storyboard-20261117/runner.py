import os,json,time,hashlib,sys,math
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator
P=Path('protoface/xie-wan-storyboard-20261117');Q=json.loads((P/'request.json').read_text());key=os.environ['PROTOFACE_API_KEY'].strip()
a=httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=120)
def call(m,p,**kw):
 r=a.request(m,p,**kw)
 if not r.is_success:raise RuntimeError(str(r.status_code)+' '+r.text[:500].replace(key,'[REDACTED]'))
 return r.json()

d=call('GET','/v1/models')
print('CATALOG '+json.dumps(d),flush=True)
