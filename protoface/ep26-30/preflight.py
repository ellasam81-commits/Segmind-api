"""Read-only H3 price/balance check. Never submits video or exposes the key."""
from pathlib import Path
import json
import os
import httpx
from packet_constraints import estimated_part
import private_transport as transport


def main():
    key = os.environ.get('PROTOFACE_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Protoface repository secret is missing')
    with httpx.Client(base_url='https://api.protoface.com', headers={'Authorization': 'Bearer ' + key}, timeout=60) as client:
        records = []
        for path in ['/v1/models/minimax/minimax-h3', '/v1/billing/quota']:
            response = client.get(path)
            if not response.is_success:
                raise RuntimeError('Read-only preflight HTTP ' + str(response.status_code))
            records.append(response.json())
    model, quota = records
    price = estimated_part(model)
    result = {'model': model, 'quota': quota, 'episodes': list(range(26, 31)),
              'clip_count': 60, 'estimated_per_clip_credits': price,
              'estimated_total_credits': 60 * price,
              'full_batch_funding_sufficient': quota.get('balance_credits', 0) >= 60 * price,
              'video_generation_submitted': False, 'provider_methods': ['GET', 'GET']}
    run = os.environ['GITHUB_RUN_ID']
    root = Path(__file__).resolve().parent
    sealed = transport.seal(json.dumps(result).encode(), (root / 'return-public.pem').read_bytes(), 'ep26-30-price-v1:' + run)
    (root / 'preflight.sealed.json').write_text(json.dumps(sealed))
    print('Read-only live price/funding check complete. Details encrypted. No video generated.')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(type(error).__name__ + ': ' + str(error).replace(os.environ.get('PROTOFACE_API_KEY') or '\x00', '[REDACTED]'))
        raise SystemExit(1)
