"""One authorized five-scene fan film, bounded cost and stable request IDs."""
import hashlib
import json
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator

ROOT = Path('protoface/thoo-color-doll-20261116')
OUT = Path('thoo-color-doll-output')
OUT.mkdir(exist_ok=True)


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    req = json.loads((ROOT / 'request.json').read_text(encoding='utf-8'))
    key = os.environ.get('PROTOFACE_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Missing PROTOFACE_API_KEY repository secret')
    with httpx.Client(base_url='https://api.protoface.com', headers={'Authorization': 'Bearer ' + key}, timeout=120) as api:
        def call(method, path, **kwargs):
            response = api.request(method, path, **kwargs)
            if not response.is_success:
                raise RuntimeError(f'Provider HTTP {response.status_code}; no replacement generation submitted')
            return response.json()

        model = call('GET', '/v1/models/minimax/minimax-h3')
        save('model.json', model)
        if model.get('available') is False:
            raise RuntimeError('Model unavailable')
        schema = model['request_schemas']['video.general']
        quality = req['quality']
        assert len(req['scenes']) == 5
        assert sum(s['duration'] for s in req['scenes']) == 60
        jobs = []
        for scene in req['scenes']:
            payload = {'operation': 'video.general', 'prompt': req['common'] + '\n' + scene['prompt'],
                       'reference': [req['reference']], 'duration_seconds': scene['duration'],
                       'quality': quality, 'aspect_ratio': '9:16', 'generate_audio': True,
                       'enhance_prompt': False}
            Draft202012Validator(schema).validate(payload)
            pricing = model['pricing']
            rule = next(x for x in pricing['add_ons'] if x['id'] == 'reference_image')['by_quality'][quality]
            cost = math.ceil(scene['duration'] * float(pricing['qualities'][quality]['credits_per_second'])
                             + max(0, 1 - int(rule.get('included', 0))) * float(rule['credits_each']))
            jobs.append((scene['n'], payload, cost))
        total = sum(j[2] for j in jobs)
        balance = float(call('GET', '/v1/billing/quota')['balance_credits'])
        save('preflight.json', {'estimated_total_credits': total, 'budget_cap': req['budget_cap'],
                                'quality': quality, 'scenes': 5, 'duration_seconds': 60})
        if total > req['budget_cap'] or balance < total:
            raise RuntimeError(f'Preflight credit cap or balance blocks generation; estimate {total}')
        print('PREFLIGHT PASSED', total, 'credits for five scenes', flush=True)
        if req.get('action') == 'preflight':
            return

        def generate(job):
            number, payload, cost = job
            label = f'scene-{number:02d}'
            digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
            submitted = call('POST', '/v1/run/' + model['id'], json=payload,
                             headers={'Idempotency-Key': req['request_id'] + '-' + label + '-' + digest})
            rid = submitted['id']
            save(label + '-submitted.json', submitted)
            print('ACCEPTED', label, rid, 'estimate', cost, flush=True)
            for attempt in range(240):
                status = call('GET', '/v1/runs/' + rid + '/status')
                save(label + '-status.json', status)
                if status['status'] in ('completed', 'failed', 'canceled'):
                    break
                time.sleep(8)
            else:
                raise RuntimeError(label + ' polling timeout; resume the same request')
            result = call('GET', '/v1/runs/' + rid)
            save(label + '-result.json', result)
            if result['status'] != 'completed':
                raise RuntimeError(label + ' ended ' + result['status'])
            outputs = [x for x in result.get('outputs', []) if x.get('modality') == 'video']
            video = result.get('video') or outputs[0]['file']
            # Media delivery always uses a separate client without the provider key.
            with httpx.Client(follow_redirects=True, timeout=240) as downloader:
                with downloader.stream('GET', video['url']) as response:
                    response.raise_for_status()
                    with (OUT / (label + '.mp4')).open('wb') as dest:
                        for chunk in response.iter_bytes():
                            dest.write(chunk)
            info = {'label': label, 'run_id': rid, 'file': video, 'credits': result.get('credits')}
            print('COMPLETE', label, rid, flush=True)
            return info

        # Concurrent independent clips share the same locked reference and full preflight.
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(generate, jobs))
        save('results.json', results)
        print('ALL FIVE CLIPS COMPLETE', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        key = os.environ.get('PROTOFACE_API_KEY', '')
        message = str(error).replace(key, '[REDACTED]') if key else str(error)
        print('STOP', type(error).__name__, message[:1000], flush=True)
        sys.exit(1)
