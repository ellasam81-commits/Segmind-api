import os,json,httpx
key=os.environ['PROTOFACE_API_KEY'].strip()
with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=90) as api:
 for mid in ['lightricks/ltx-2.5-fast','minimax/minimax-h3','openai/gpt-image-2']:
  r=api.get('/v1/models/'+mid);r.raise_for_status();print('MODEL '+json.dumps(r.json()),flush=True)
