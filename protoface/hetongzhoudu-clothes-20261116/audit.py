import os,json,httpx
key=os.environ['PROTOFACE_API_KEY'].strip()
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=60) as api:
 def get(path):
  r=api.get(path);r.raise_for_status();return r.json()
 q=get('/v1/billing/quota');print('QUOTA',json.dumps(q),flush=True)
 for mid in ['pruna-ai/p-video-replace','openai/gpt-image-2','kuaishou/kling-video-o1-fast']:
  m=get('/v1/models/'+mid)
  print('MODEL_SCHEMA',json.dumps(m,ensure_ascii=False),flush=True)
