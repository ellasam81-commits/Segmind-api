"""Independent T Hoo Hoo Protoface runner. No imports from drama projects."""
import hashlib
import json
import os
import time
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator

OUT = Path('thoo-hoo-output')
MODEL = 'minimax/minimax-h3'


def save(name, data):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    key = os.environ.get('PROTOFACE_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Missing PROTOFACE_API_KEY repository secret')
    action = os.environ.get('ACTION', 'check_connection')
    with httpx.Client(base_url='https://api.protoface.com', headers={'Authorization': 'Bearer ' + key}, timeout=60) as client:
        def api(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            if not response.is_success:
                raise RuntimeError(f'Protoface HTTP {response.status_code}; no automatic resubmission')
            return response.json()

        if action == 'check_connection':
            api('GET', '/v1/models')
            print('Protoface connection successful. No paid generation submitted.')
            return
        model = api('GET', '/v1/models/' + MODEL)
        save('model.json', model)
        if action == 'inspect_model':
            print('Saved current model schema and pricing. No paid generation submitted.')
            return
        if action != 'generate_part':
            raise ValueError('Unsupported action')
        if os.environ.get('CONFIRM_SPEND', '').lower() != 'true':
            raise ValueError('Paid generation requires confirm_spend=true')
        part = int(os.environ.get('PART', '1'))
        if part not in range(1, 6):
            raise ValueError('Part must be 1 through 5')
        prompt = os.environ.get('PROMPT', '').strip()
        reference = os.environ.get('REFERENCE_IMAGE_URL', '').strip()
        if not prompt or not reference.startswith('https://'):
            raise ValueError('Supply a reviewed prompt and HTTPS reference image URL')
        payload = dict(prompt=prompt, reference=[reference], duration_seconds=12,
                       quality=os.environ.get('QUALITY', '480p'), aspect_ratio='16:9',
                       generate_audio=True, enhance_prompt=False)
        schema = model.get('request_schemas', {}).get('video.general')
        if not schema or model.get('available') is False:
            raise ValueError('Model unavailable or schema missing')
        if len(model.get('operations', {})) > 1:
            payload['operation'] = 'video.general'
        Draft202012Validator(schema).validate(payload)
        ceiling = float(os.environ.get('MAX_CREDITS', '0'))
        pricing = model['pricing']
        quality = payload['quality']
        estimate = 12 * float(pricing['qualities'][quality]['credits_per_second'])
        rule = next(r for r in pricing['add_ons'] if r['id'] == 'reference_image')['by_quality'][quality]
        estimate += max(0, 1 - int(rule.get('included', 0))) * float(rule['credits_each'])
        if ceiling <= 0 or estimate > ceiling:
            raise ValueError(f'Estimated {estimate} credits exceeds configured limit; nothing submitted')
        quota = api('GET', '/v1/billing/quota')
        if float(quota.get('balance_credits', 0)) < estimate:
            raise ValueError('Insufficient credits; nothing submitted')
        identity = os.environ['GITHUB_RUN_ID']
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
        checkpoint = OUT / 'checkpoint.json'
        state = json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
        if state and state.get('digest') != digest:
            raise ValueError('Checkpoint input mismatch')
        if not state.get('run_id'):
            created = api('POST', '/v1/run/' + MODEL, json=payload,
                          headers={'Idempotency-Key': f'thoo-hoo-{identity}-part{part}-{digest}'})
            state = dict(run_id=created['id'], digest=digest, part=part, estimate=estimate)
            save('checkpoint.json', state)
            save('submitted.json', created)
        deadline = time.monotonic() + 1500
        while time.monotonic() < deadline:
            status = api('GET', f"/v1/runs/{state['run_id']}/status")
            save('status.json', status)
            if status['status'] in ('completed', 'failed', 'canceled'):
                result = api('GET', f"/v1/runs/{state['run_id']}")
                save('result.json', result)
                print('T Hoo Hoo part', part, status['status'], state['run_id'])
                if status['status'] != 'completed':
                    raise RuntimeError('Provider did not complete. No replacement submitted.')
                return
            time.sleep(10)
        raise RuntimeError('Polling timed out. Re-run this same workflow run to resume; do not create a new paid run.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        key = os.environ.get('PROTOFACE_API_KEY', '')
        message = str(exc)
        print(message.replace(key, '[REDACTED]') if key else message)
        raise SystemExit(1)
