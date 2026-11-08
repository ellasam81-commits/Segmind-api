"""Authorized independent five-part tutorial. Never touches other project paths."""
import json, os
from pathlib import Path
import run

request=json.loads(Path('protoface/thoo-hoo-qqmusic/generation-request.json').read_text())
assert request['max_total_credits']==75 and len(request['parts'])==5
assert [p['part'] for p in request['parts']]==list(range(1,6))
os.environ.update(ACTION='generate_part',CONFIRM_SPEND='true',QUALITY='480p',MAX_CREDITS='15')
# Stable request identity also protects against re-triggering the same manifest.
os.environ['GITHUB_RUN_ID']=request['request_id']
root=Path('thoo-hoo-output');root.mkdir(exist_ok=True)
for p in request['parts']:
 run.OUT=root/('part-'+str(p['part']));run.OUT.mkdir(exist_ok=True)
 os.environ.update(PART=str(p['part']),PROMPT=p['prompt'],REFERENCE_IMAGE_URL=p['reference'])
 run.main()
print('All five tutorial generations completed; no replacement jobs submitted.')
