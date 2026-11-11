"""GET-only price/model/quota inspection; never submits generation."""
from pathlib import Path
from decimal import Decimal
import json,os
import httpx
import private_transport as transport
ROOT=Path(__file__).resolve().parent
def main():
    secret=os.environ.get('PROTOFACE_API_KEY','').strip()
    if not secret: raise RuntimeError('Existing repository provider secret is unavailable')
    values=[]
    with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+secret},timeout=60,follow_redirects=False)as client:
        for route in ['/v1/models/minimax/minimax-h3','/v1/billing/quota']:
            response=client.get(route)
            if not response.is_success:raise RuntimeError('Read-only provider HTTP '+str(response.status_code))
            values.append(response.json())
    model,quota=values;p=model['pricing']
    rule=next(x for x in p['add_ons']if x['id']=='reference_image')['by_quality']['480p']
    quote=Decimal('5')*Decimal(str(p['qualities']['480p']['credits_per_second']))+max(Decimal('0'),Decimal('1')-Decimal(str(rule.get('included',0))))*Decimal(str(rule['credits_each']))
    result={'model':model,'quota':quota,'requested_episodes':list(range(51,61)),'clips':120,'per_clip_credits':float(quote),'total_video_credits':float(120*quote),'per_clip_cap_credits':8,'total_video_cap_credits':960,'within_quote_cap':quote<=8,'full_batch_funding_sufficient':Decimal(str(quota.get('balance_credits',0)))>=120*quote,'provider_methods':['GET','GET'],'generation_submitted':False}
    run=os.environ['GITHUB_RUN_ID']
    envelope=transport.seal(json.dumps(result).encode(),(ROOT/'return-public.pem').read_bytes(),'ep51-60-final20261112-price:'+run)
    (ROOT/'preflight.sealed.json').write_text(json.dumps(envelope))
    print('Read-only model and funding check finished; exact figures encrypted. No generation submitted.',flush=True)
if __name__=='__main__':
    try:main()
    except Exception as e:
        secret=os.environ.get('PROTOFACE_API_KEY')or'\0'
        print(type(e).__name__+': '+str(e).replace(secret,'[REDACTED]'))
        raise SystemExit(1)
