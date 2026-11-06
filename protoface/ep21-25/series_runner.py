"""Generic Actions worker. Private story inputs and outputs are always encrypted in transit."""
from pathlib import Path
import argparse
import base64
import io
import json
import os
import re
import shutil
import subprocess
import time
import zipfile
import httpx
from jsonschema import Draft202012Validator, ValidationError
from config import ROOT, AAD_PREFIX, REMOTE_ROOT, EPISODES, PARTS, MODEL
import private_transport as transport
from packet_constraints import estimated_part, payload, input_signature, request_key, validate_packet


def save(path, data):
    transport.write_private(path, json.dumps(data, ensure_ascii=False, indent=2).encode())


def api(client, method, path, **kwargs):
    for attempt in range(4):
        response = client.request(method, path, **kwargs)
        if response.status_code in (502, 503, 504) and method == 'GET' and attempt < 3:
            time.sleep(3 * (attempt + 1))
            continue
        if not response.is_success:
            try:
                code = response.json().get('error', {}).get('code', 'provider_request_failed')
            except Exception:
                code = 'provider_request_failed'
            raise RuntimeError(f'Provider HTTP {response.status_code}: {code}')
        return response.json()


def provider():
    key = os.environ.get('PROTOFACE_API_KEY', '').strip()
    if not key:
        raise RuntimeError('Provider secret is missing')
    return httpx.Client(base_url='https://api.protoface.com', headers={'Authorization': 'Bearer ' + key}, timeout=90, follow_redirects=False)


def selected_parts(value):
    parts = [int(x) for x in value.split(',')] if value else []
    if len(parts) != len(set(parts)) or any(p not in PARTS for p in parts):
        raise ValueError('Invalid reviewed repair selection')
    return parts


def init(episode, run_id, private_dir):
    parts = selected_parts(os.environ.get('REVIEWED_REPAIR_PARTS', ''))
    repair_id = os.environ.get('REVIEWED_REPAIR_ID', '')
    if bool(parts) != bool(repair_id):
        raise ValueError('Reviewed repair parts and request identity must be provided together')
    if not run_id or private_dir is None:
        raise ValueError('Run identity and ephemeral key folder are required')
    public_dir = ROOT / f'transport-public/ep{episode:02}'
    # init is read-only against the provider: GET model and GET quota only.
    with provider() as client:
        model = api(client, 'GET', '/v1/models/' + MODEL)
        quota = api(client, 'GET', '/v1/billing/quota')
    if not model.get('available'):
        raise RuntimeError('H3 is unavailable; no input channel or paid request created')
    price = estimated_part(model)
    count = len(parts) if parts else 60
    funding_count = len(parts) if parts else (60 if episode == 21 else 12)
    funding_required = funding_count * price
    funding_sufficient = quota.get('balance_credits', 0) >= funding_required
    transport.init(private_dir, public_dir, run_id)
    ready_path = public_dir / 'ready.json'
    ready = json.loads(ready_path.read_text())
    ready.update(episode=episode, parts=parts or list(PARTS), protocol='ep21-25-three5-v1',
                 request_kind='repair' if parts else 'initial', repair_request_id=repair_id or None,
                 maximum_credits_per_attempt=8, maximum_additional_generations_per_defective_clip=1)
    save(ready_path, ready)
    details = {'model': model, 'quota': quota, 'estimated_per_clip': price, 'episode_count': 1 if parts else 5,
               'clip_count': count, 'estimated_batch_credits': count * price, 'maximum_initial_batch_credits': 480,
               'generation_submitted': False, 'request_kind': ready['request_kind'], 'funding_check_clip_count': funding_count,
               'funding_required_credits': funding_required, 'funding_sufficient': funding_sufficient,
               'full_initial_batch_funding_sufficient': quota.get('balance_credits', 0) >= 60 * price}
    public = (ROOT / 'return-public.pem').read_bytes()
    save(public_dir / 'preflight.sealed.json', transport.seal(json.dumps(details).encode(), public,
         f'{AAD_PREFIX}-preflight-v1:{run_id}:ep{episode:02}'))
    print('Read-only live model price and batch funding checked; funding sufficient:', funding_sufficient,
          '; private figures encrypted. No generation submitted.', flush=True)


def receive(episode, run_id, private_dir, repository):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository or ''):
        raise ValueError('Invalid repository identity')
    ready = json.loads((ROOT / f'transport-public/ep{episode:02}/ready.json').read_text())
    if ready.get('run_id') != run_id or ready.get('episode') != episode:
        raise ValueError('Input channel identity mismatch')
    private = (private_dir / 'input-private.pem').read_bytes()
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'ThirteenDoors-encrypted-input'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    work = ROOT / f'work/ep{episode:02}'
    pending = set(ready['parts'])
    deadline = time.monotonic() + 19200
    with httpx.Client(headers=headers, timeout=60, follow_redirects=False) as client:
        while pending and time.monotonic() < deadline:
            remote_folder = f'{REMOTE_ROOT}/private-inputs/{run_id}'
            listing = client.get(f'https://api.github.com/repos/{repository}/contents/{remote_folder}', params={'ref': 'main'})
            if listing.status_code == 404:
                time.sleep(30)
                continue
            listing.raise_for_status()
            available = {x['name'] for x in listing.json()}
            for part in sorted(pending):
                remote = f'{remote_folder}/ep-{episode:02}-part-{part:02}.enc.json'
                if remote.rsplit('/', 1)[1] not in available:
                    continue
                response = client.get(f'https://api.github.com/repos/{repository}/contents/{remote}', params={'ref': 'main'})
                if response.status_code == 404:
                    continue
                response.raise_for_status()
                record = response.json()
                if record.get('encoding') != 'base64':
                    raise RuntimeError('Encrypted input exceeds inline transport limit')
                envelope = json.loads(base64.b64decode(record['content']))
                aad = f'{AAD_PREFIX}-native-v1:{run_id}:ep{episode:02}:part{part:02}:{ready["session_nonce"]}'
                plain = transport.unseal(envelope, private, aad)
                packet = validate_packet(json.loads(plain), episode, part)
                if packet.get('request_kind', 'initial') != ready['request_kind'] or packet.get('repair_request_id') != ready.get('repair_request_id'):
                    raise ValueError('Private request scope differs from the reviewed input channel')
                transport.write_private(work / f'packets/part-{part:02}.json', plain)
                if packet.get('resume_state'):
                    save(work / f'state/part-{part:02}.json', packet['resume_state'])
                pending.remove(part)
                print('Reviewed private input received:', episode, part, flush=True)
            if pending:
                time.sleep(30)
    if pending:
        raise TimeoutError('Storyboard inputs still missing; no paid request submitted')


def ffmpeg():
    executable = shutil.which('ffmpeg')
    if executable:
        return executable
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def media(command, description):
    result = subprocess.run([ffmpeg(), '-nostdin', '-v', 'error', '-y'] + command,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(description + '; original media and request checkpoint are preserved')
    return result.stdout


def audio_duration(path):
    output = media(['-i', str(path), '-map', '0:a:0', '-vn', '-c:a', 'pcm_s16le', '-f', 'null', '-', '-progress', 'pipe:1'], 'Native audio verification failed')
    timings = [int(x) for x in re.findall(rb'out_time_us=(\d+)', output)]
    if not timings:
        raise RuntimeError('Native audio timing is unavailable')
    return max(timings) / 1000000


def normalize(raw, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    source_audio = audio_duration(raw)
    if not 4.75 <= source_audio <= 5.10:
        raise RuntimeError('Source native audio requires timing review; no automatic truncation or replacement')
    media(['-threads', '2', '-filter_threads', '1', '-i', str(raw), '-map', '0:v:0', '-map', '0:a:0', '-sn', '-dn',
           '-vf', 'fps=24,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=0.3',
           '-t', '5', '-frames:v', '120', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p',
           '-af', 'apad=pad_dur=0.3,atrim=duration=5,asetpts=PTS-STARTPTS', '-ar', '32000', '-ac', '2', '-c:a', 'aac', '-b:a', '192k',
           '-movflags', '+faststart', str(target)], 'Native clip normalization failed')
    target_audio = audio_duration(target)
    if not 4.98 <= target_audio <= 5.10:
        raise RuntimeError('Normalized clip audio does not cover the full five-second slot')
    return {'source_audio_seconds': source_audio, 'normalized_audio_seconds': target_audio, 'native_audio': True}


def generate_one(episode, part, packet):
    validate_packet(packet, episode, part)
    work = ROOT / f'work/ep{episode:02}'
    state_path = work / f'state/part-{part:02}.json'
    raw = work / f'raw/part-{part:02}.mp4'
    target = work / f'clips/part-{part:02}.mp4'
    signature, identity = input_signature(packet), request_key(packet)
    state = json.loads(state_path.read_text()) if state_path.exists() else {
        'idempotency_key': identity, 'input_sha256': signature, 'request_kind': packet.get('request_kind', 'initial'),
        'repair_request_id': packet.get('repair_request_id'), 'episode': episode, 'part': part,
    }
    if state.get('idempotency_key') != identity or state.get('input_sha256') != signature:
        raise RuntimeError('Checkpoint input mismatch; existing request will not be replaced')
    with provider() as client:
        if not state.get('run_id'):
            if state.get('submission_uncertain'):
                raise RuntimeError('Submission outcome uncertain; recover the same request instead of buying a replacement')
            # The intent is durable before the sole POST. A timeout/5xx keeps it
            # uncertain and blocks another POST until the original is reconciled.
            state['submission_uncertain'] = True
            save(state_path, state)
            response = client.post('/v1/run/' + MODEL, headers={'Idempotency-Key': identity}, json=payload(packet))
            if not response.is_success:
                state['submission_http_status'] = response.status_code
                if response.status_code in (400, 401, 403, 404, 422, 429):
                    state['submission_uncertain'] = False  # explicit rejection, no accepted run
                save(state_path, state)
                raise RuntimeError(f'Generation submission HTTP {response.status_code}; no automatic paid retry')
            created = response.json()
            # Malformed success responses stay uncertain; never substitute a new request.
            if not created.get('id'):
                raise RuntimeError('Accepted submission response lacks its run ID; reconcile the existing request')
            state.update(run_id=created['id'], status=created.get('status'), credit_estimate=created.get('credit_estimate'), submission_uncertain=False)
            save(state_path, state)
            print('Accepted native part:', episode, part, state['run_id'], flush=True)
        deadline = time.monotonic() + 2400
        previous = None
        while time.monotonic() < deadline:
            status = api(client, 'GET', f'/v1/runs/{state["run_id"]}/status')
            state['status'] = status['status']
            save(state_path, state)
            if state['status'] != previous:
                print('Part state:', episode, part, state['status'], flush=True)
                previous = state['status']
            if state['status'] in ('failed', 'canceled'):
                raise RuntimeError('Accepted provider run ended without output; no automatic paid replacement')
            if state['status'] == 'completed':
                result = api(client, 'GET', f'/v1/runs/{state["run_id"]}')
                state['credits'] = result.get('credits')
                save(state_path, state)
                url = (result.get('video') or {}).get('url')
                if not url:
                    url = next((x.get('file', {}).get('url') for x in result.get('outputs', []) if x.get('modality') == 'video'), None)
                if not url:
                    raise RuntimeError('Completed run lacks a movie URL')
                parsed = httpx.URL(url)
                if parsed.scheme != 'https' or parsed.userinfo:
                    raise ValueError('Unexpected media URL')
                raw.parent.mkdir(parents=True, exist_ok=True)
                # Asset downloader has no provider Authorization header.
                with httpx.Client(timeout=120, follow_redirects=True) as downloader:
                    with downloader.stream('GET', url) as response:
                        response.raise_for_status()
                        with raw.open('wb') as stream:
                            for chunk in response.iter_bytes():
                                stream.write(chunk)
                state['audio_timing'] = normalize(raw, target)
                save(state_path, state)
                return state
            time.sleep(5)
    raise TimeoutError('Accepted run remains pending; preserve its ID and poll the same run later')


def generate(episode, parts=None):
    if os.environ.get('ALLOW_PAID_GENERATION') != 'true':
        raise RuntimeError('Generation authorization is absent')
    numbers = parts or list(PARTS)
    work = ROOT / f'work/ep{episode:02}'
    packets = {n: validate_packet(json.loads((work / f'packets/part-{n:02}.json').read_text()), episode, n) for n in numbers}
    if any(p.get('request_kind', 'initial') != ('repair' if parts else 'initial') for p in packets.values()):
        raise ValueError('Selected generation scope mismatch')
    if parts and any(p.get('repair_request_id') != os.environ.get('REVIEWED_REPAIR_ID') for p in packets.values()):
        raise ValueError('Reviewed repair identity mismatch')
    with provider() as client:
        model = api(client, 'GET', '/v1/models/' + MODEL)
        if not model.get('available'):
            raise RuntimeError('H3 is unavailable')
        estimates = {}
        for number, packet in packets.items():
            estimates[number] = estimated_part(model, packet)
            try:
                Draft202012Validator(model['request_schemas']['video.general']).validate(payload(packet))
            except ValidationError:
                raise RuntimeError('Private request schema validation failed; private input was not logged') from None
        quota = api(client, 'GET', '/v1/billing/quota')
        # Known accepted runs cost nothing to poll. Only unsubmitted packets
        # count toward the fresh funding requirement.
        unsubmitted = []
        for n, packet in packets.items():
            path = work / f'state/part-{n:02}.json'
            state = json.loads(path.read_text()) if path.exists() else packet.get('resume_state', {})
            if not state.get('run_id'):
                unsubmitted.append(n)
        estimate = sum(estimates[n] for n in unsubmitted)
        if quota.get('balance_credits', 0) < estimate:
            raise RuntimeError('Live balance does not cover the selected unsubmitted parts')
    print('Reviewed inputs and live quote validated:', episode, 'maximum fresh credits', estimate, flush=True)
    states = [generate_one(episode, n, packets[n]) for n in numbers]
    report = {'episode': episode, 'title': packets[numbers[0]]['title'], 'parts': states, 'tts_used': False, 'post_dubbing': False,
              'subtitles_and_corner_credits': 'Applied locally after actual native-speech review.'}
    if parts:
        report['reviewed_replacement_parts'] = numbers
    else:
        listing = work / 'concat.txt'
        listing.write_text(''.join(f"file '{work / f'clips/part-{n:02}.mp4'}'\n" for n in PARTS))
        media(['-threads', '2', '-f', 'concat', '-safe', '0', '-i', str(listing), '-map', '0:v:0', '-map', '0:a:0',
               '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', str(work / 'episode-native.mp4')], 'Episode native assembly failed')
        duration = audio_duration(work / 'episode-native.mp4')
        if not 59.98 <= duration <= 60.20:
            raise RuntimeError('Assembled native audio does not cover the full sixty seconds')
        report['assembled_audio_seconds'] = duration
    save(work / 'generation-report.json', report)
    print('Selected native parts complete:', episode, numbers, flush=True)


def seal_results(episode, run_id):
    work = ROOT / f'work/ep{episode:02}'
    paths = []
    # Preserve every raw native clip, not just failed normalization sources.
    for pattern in ('raw/*.mp4', 'clips/*.mp4', 'state/*.json', 'episode-native.mp4', 'generation-report.json'):
        paths.extend(work.glob(pattern))
    if not paths:
        print('No provider checkpoint or generated media exists to export.', flush=True)
        return
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w', zipfile.ZIP_STORED) as archive:
        for path in sorted(set(paths)):
            archive.write(path, f'ep{episode:02}/' + str(path.relative_to(work)))
    public = (ROOT / 'return-public.pem').read_bytes()
    save(ROOT / f'sealed-results/ep{episode:02}.sealed.json', transport.seal(data.getvalue(), public,
         f'{AAD_PREFIX}-result-v1:{run_id}:ep{episode:02}'))
    print('Selected outputs and accepted request checkpoints encrypted for local return:', episode, flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['init', 'receive', 'generate', 'seal'])
    parser.add_argument('--episode', type=int, required=True, choices=EPISODES)
    parser.add_argument('--run-id', type=int)
    parser.add_argument('--private-dir', type=Path)
    parser.add_argument('--repository')
    parser.add_argument('--part', type=int, choices=PARTS)
    parser.add_argument('--parts')
    args = parser.parse_args()
    if args.mode == 'init':
        init(args.episode, args.run_id, args.private_dir)
    elif args.mode == 'receive':
        receive(args.episode, args.run_id, args.private_dir, args.repository)
    elif args.mode == 'generate':
        parts = selected_parts(args.parts) if args.parts else ([args.part] if args.part else None)
        generate(args.episode, parts)
    else:
        if not args.run_id:
            raise ValueError('A result run identity is required')
        seal_results(args.episode, args.run_id)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Never log tracebacks, private bodies, source images or credentials.
        print(str(exc).replace(os.environ.get('PROTOFACE_API_KEY') or '\x00', '[REDACTED]'), flush=True)
        raise SystemExit(1)
