"""Read current H3 capabilities and funding, without submitting any paid run."""
from pathlib import Path
import json
import os
import sys

import httpx

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'ep01-c01'))
import private_transport


def main():
    key=os.environ.get('PROTOFACE_API_KEY','').strip()
    if not key:raise RuntimeError('Repository secret PROTOFACE_API_KEY is missing')
    with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},
                      timeout=90,follow_redirects=False) as client:
        responses=[]
        for path in ['/v1/models/minimax/minimax-h3','/v1/billing/quota']:
            response=client.get(path)
            if not response.is_success:raise RuntimeError(f'Read-only provider check failed: HTTP {response.status_code}')
            responses.append(response.json())
    model,quota=responses
    pricing=model['pricing'];part=15*pricing['qualities']['480p']['credits_per_second']
    rule=next(x for x in pricing['add_ons'] if x['id']=='reference_image')['by_quality']['480p']
    part+=max(0,1-rule.get('included',0))*rule['credits_each']
    total=36*part;balance=quota.get('balance_credits',0)
    result={'model':model,'quota':quota,'part_count':36,'estimated_credits_per_part':part,
            'estimated_total_credits':total,'balance_covers_full_batch':balance>=total,
            'balance_covers_one_episode':balance>=4*part,'price_within_previous_limit':part<=18,
            'generation_submitted':False}
    public=(ROOT.parent/'ep01-c01/return-public.pem').read_bytes()
    envelope=private_transport.seal(json.dumps(result).encode(),public,'ep02-10-read-only-preflight-v1')
    out=ROOT/'preflight-output';out.mkdir(exist_ok=True)
    (out/'preflight.sealed.json').write_text(json.dumps(envelope,separators=(',',':')))
    # Billing details and capabilities are encrypted, never logged to the public run.
    print('Read-only model and funding check completed. No generation submitted.')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc).replace(os.environ.get('PROTOFACE_API_KEY') or '\x00','[REDACTED]'))
        raise SystemExit(1)
