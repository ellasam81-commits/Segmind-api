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
import tempfile
import time
import wave
import zipfile
import httpx
from jsonschema import Draft202012Validator, ValidationError
from config import ROOT, AAD_PREFIX, REMOTE_ROOT, EPISODES, PARTS, MODEL, parts_for, INITIAL_CLIP_COUNT, INITIAL_CREDITS
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
    initial_parts = selected_parts(os.environ.get('INITIAL_PARTS', ''))
    if parts and initial_parts:
        raise ValueError('Initial pilot and quality-repair selections cannot be mixed')
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
    selection = parts or initial_parts
    count = len(selection) if selection else INITIAL_CLIP_COUNT
    funding_count = len(selection) if selection else len(parts_for(episode))
    if any(n not in parts_for(episode) for n in selection):
        raise ValueError("Selected part outside this episode")
    funding_required = funding_count * price
    funding_sufficient = quota.get('balance_credits', 0) >= funding_required
    transport.init(private_dir, public_dir, run_id)
    ready_path = public_dir / 'ready.json'
    ready = json.loads(ready_path.read_text())
    ready.update(episode=episode, parts=parts or initial_parts or list(parts_for(episode)), initial_part_selection=bool(initial_parts), protocol='ep51-60-final-three5-v1',
                 request_kind='repair' if parts else 'initial', repair_request_id=repair_id or None,
                 maximum_credits_per_attempt=8, maximum_additional_generations_per_defective_clip=1)
    save(ready_path, ready)
    details = {'model': model, 'quota': quota, 'estimated_per_clip': price, 'episode_count': 1,
               'clip_count': count, 'estimated_batch_credits': count * price, 'maximum_initial_batch_credits': INITIAL_CREDITS,
               'generation_submitted': False, 'request_kind': ready['request_kind'], 'funding_check_clip_count': funding_count,
               'funding_required_credits': funding_required, 'funding_sufficient': funding_sufficient,
               'full_initial_batch_funding_sufficient': quota.get('balance_credits', 0) >= INITIAL_CLIP_COUNT * price}
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
            listing = client.get(f'https://api.github.com/repos/{repository}/contents/{remote_folder}', params={'ref': os.environ.get('TD_INPUT_REF', 'main')})
            if listing.status_code == 404:
                time.sleep(30)
                continue
            listing.raise_for_status()
            available = {x['name'] for x in listing.json()}
            for part in sorted(pending):
                remote = f'{remote_folder}/ep-{episode:02}-part-{part:02}.enc.json'
                if remote.rsplit('/', 1)[1] not in available:
                    continue
                response = client.get(f'https://api.github.com/repos/{repository}/contents/{remote}', params={'ref': os.environ.get('TD_INPUT_REF', 'main')})
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


def video_duration(path):
    output = media(['-threads', '2', '-i', str(path), '-map', '0:v:0', '-an', '-f', 'null', '-', '-progress', 'pipe:1'], 'Native video timing verification failed')
    timings = [int(x) for x in re.findall(rb'out_time_us=(\d+)', output)]
    if not timings:
        raise RuntimeError('Native video timing is unavailable')
    return max(timings) / 1000000


def normalize(raw, target):
    """Fit the complete bounded native take into its slot, without tail cuts.

    H3 may return about 5.17 seconds for a five-second request. A uniform
    pitch-preserving audio tempo change and matching picture retime keep all
    source content. Only silence is appended after the complete retimed sound.
    AAC packet padding is reported separately from the exact five-second PCM.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    source_audio = audio_duration(raw)
    source_video = video_duration(raw)
    if not all(4.75 <= duration <= 5.35 for duration in (source_audio, source_video)) or abs(source_audio - source_video) > .15:
        raise RuntimeError('Source native timing lies outside the bounded retime window; preserve it for review, no replacement purchased')
    tempo = max(source_audio, source_video) / 5
    exact_frames, rate, channels, frame_bytes = 160000, 32000, 2, 4
    with tempfile.TemporaryDirectory(prefix='native-retime-', dir=target.parent) as directory:
        temporary = Path(directory)
        retimed_pcm = None
        for attempt in range(6):
            retimed_pcm = media(['-threads', '2', '-i', str(raw), '-map', '0:a:0', '-vn', '-af', f'atempo={tempo:.12f}',
                '-ar', str(rate), '-ac', str(channels), '-c:a', 'pcm_s16le', '-f', 's16le', 'pipe:1'], 'Complete native audio retime failed')
            if len(retimed_pcm) % frame_bytes:
                raise RuntimeError('Retimed native PCM has a partial sample frame')
            content_frames = len(retimed_pcm) // frame_bytes
            if content_frames <= exact_frames:
                break
            # atempo's overlap windows can overshoot by a few milliseconds.
            # Reprocess the full source a little faster; never trim its tail.
            tempo *= content_frames / exact_frames + .001
            if tempo > 1.085:
                raise RuntimeError('Native take would require more than the bounded small tempo adjustment')
        else:
            raise RuntimeError('Complete native sound could not fit the slot without trimming; source preserved')
        if content_frames < int(4.80 * rate):
            raise RuntimeError('Retimed source has excessive missing slot coverage; inspect source timing')
        silence_frames = exact_frames - content_frames
        wav_path = temporary / 'complete-native-five-seconds.wav'
        with wave.open(str(wav_path), 'wb') as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(2)
            wav.setframerate(rate)
            wav.writeframes(retimed_pcm + b'\0' * silence_frames * frame_bytes)
        picture = temporary / 'picture-only.mp4'
        media(['-threads', '2', '-filter_threads', '1', '-i', str(raw), '-map', '0:v:0', '-an', '-sn', '-dn',
            '-vf', f'setpts=(PTS-STARTPTS)/{tempo:.12f},fps=24,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=1',
            '-frames:v', '120', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '18', '-threads', '2', '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart', str(picture)], 'Native picture retime failed')
        staged = temporary / 'normalized.mp4'
        # No -t, -shortest, frame cap or trim touches this complete sound input.
        media(['-i', str(picture), '-i', str(wav_path), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k', '-ar', str(rate), '-ac', str(channels), '-movflags', '+faststart', str(staged)],
            'Complete native clip mux failed')
        target_audio = audio_duration(staged)
        target_video = video_duration(staged)
        if not 4.999 <= target_video <= 5.001 or not 4.999 <= target_audio <= 5.05:
            raise RuntimeError('Normalized native slot timing verification failed; source preserved')
        staged.replace(target)
    return {'source_audio_seconds': source_audio, 'source_video_seconds': source_video,
            'normalized_audio_seconds': target_audio, 'normalized_video_seconds': target_video,
            'exact_pcm_seconds': exact_frames / rate, 'retimed_audio_content_seconds': content_frames / rate,
            'trailing_silence_seconds': silence_frames / rate, 'uniform_tempo_factor': tempo,
            'audio_pitch_preserved': True, 'full_source_audio_processed': True, 'source_audio_tail_trimmed': False,
            'native_audio': True, 'post_dubbing': False}


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
                state['output_video_url'] = url
                save(state_path, state)
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


def assemble_native_exact_slots(work):
    """Join twelve normalized five-second native slots with one AAC encode.

    normalize() must already preserve each original clip's complete intended
    native content in its approved five-second slot. The extra decoded samples
    removed here are limited to padding from those controlled normalized AAC
    clips. This helper never repairs or truncates an unnormalized provider file.
    """
    import hashlib

    numbers = parts_for(int(work.name.removeprefix("ep")))
    clip_count = len(numbers)
    duration = clip_count * 5
    rate, channels, bytes_per_sample = 32000, 2, 2
    samples_per_slot = 5 * rate
    bytes_per_slot = samples_per_slot * channels * bytes_per_sample
    files = [work / f'clips/part-{number:02}.mp4' for number in numbers]
    if len(files) != clip_count or any(not path.is_file() for path in files):
        raise RuntimeError('The complete reviewed normalized clip count are required for assembly')
    before = {str(number): hashlib.sha256(path.read_bytes()).hexdigest() for number, path in zip(numbers, files)}
    assembly = work / 'assembly-temp'
    assembly.mkdir(parents=True, exist_ok=True)
    listing = assembly / 'picture-concat.txt'
    picture = assembly / 'picture-only.mp4'
    pcm = assembly / 'native-exact-slots.s16le'
    staged = work / 'episode-native.assembling.mp4'
    target = work / 'episode-native.mp4'

    def quote(path):
        return str(path.resolve()).replace("'", "'\\''")

    # Demux only picture. Explicit slot durations prevent an input container's
    # audio padding from moving the next picture's starting timestamp.
    listing.write_text(''.join("file '" + quote(path) + "'\nduration 5.000000\n" for path in files))
    media(['-threads', '2', '-f', 'concat', '-safe', '0', '-i', str(listing),
           '-map', '0:v:0', '-an', '-c:v', 'copy', '-movflags', '+faststart', str(picture)],
          'Picture-only native assembly failed')

    padding = {}
    with pcm.open('wb') as timeline:
        for number, path in zip(numbers, files):
            decoded = media(['-threads', '2', '-i', str(path), '-map', '0:a:0', '-vn',
                             '-ar', str(rate), '-ac', str(channels), '-c:a', 'pcm_s16le',
                             '-f', 's16le', 'pipe:1'], 'Native slot PCM decoding failed')
            frame_size = channels * bytes_per_sample
            if len(decoded) % frame_size:
                raise RuntimeError('Native PCM ended with an incomplete sample frame')
            sample_count = len(decoded) // frame_size
            if not samples_per_slot <= sample_count <= samples_per_slot + 2048:
                raise RuntimeError('Normalized native audio requires timing review; no assembly padding or truncation applied')
            padding[str(number)] = sample_count - samples_per_slot
            timeline.write(decoded[:bytes_per_slot])
    if pcm.stat().st_size != clip_count * bytes_per_slot:
        raise RuntimeError('Native audio timeline does not contain the reviewed exact five-second sample slots')

    # The PCM input has exactly sixty seconds. No shortest/duration switch may
    # hide an audio deficit. Encode this complete native timeline only once.
    media(['-threads', '2', '-i', str(picture), '-f', 's16le', '-ar', str(rate), '-ac', str(channels), '-i', str(pcm),
           '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-ar', str(rate), '-ac', str(channels),
           '-b:a', '192k', '-movflags', '+faststart', str(staged)], 'Exact native sample-slot assembly failed')
    decoded_master = media(['-threads', '2', '-i', str(staged), '-map', '0:a:0', '-vn', '-c:a', 'pcm_s16le',
                            '-ar', str(rate), '-ac', str(channels), '-f', 's16le', 'pipe:1'],
                           'Assembled native audio verification failed')
    master_samples = len(decoded_master) // (channels * bytes_per_sample)
    expected_samples = clip_count * samples_per_slot
    if len(decoded_master) % (channels * bytes_per_sample) or not expected_samples <= master_samples <= expected_samples + 1024:
        raise RuntimeError('Assembled native audio does not cover sixty exact seconds within codec padding tolerance')
    picture_check = media(['-threads', '2', '-i', str(staged), '-map', '0:v:0', '-an',
                           '-fps_mode', 'passthrough', '-f', 'null', '-', '-progress', 'pipe:1'],
                          'Assembled native picture verification failed')
    frame_counts = [int(value) for value in re.findall(rb'frame=(\d+)', picture_check)]
    frame_times = [int(value) for value in re.findall(rb'out_time_us=(\d+)', picture_check)]
    if not frame_counts or max(frame_counts) != duration * 24 or not frame_times or abs(max(frame_times) / 1000000 - duration) > 0.055:
        raise RuntimeError('Assembled picture does not contain the reviewed frame count and duration')
    if any(hashlib.sha256(path.read_bytes()).hexdigest() != before[str(number)] for number, path in zip(numbers, files)):
        raise RuntimeError('A selected source clip changed during assembly; previous master is preserved')
    staged.replace(target)
    picture.unlink()
    pcm.unlink()
    return {'assembled_audio_seconds': master_samples / rate,
            'assembled_audio_sample_rate': rate, 'assembled_audio_channels': channels,
            'native_audio_assembly': f'{clip_count} exact five-second native PCM slots; one master AAC encode',
            'native_audio_samples_per_slot': samples_per_slot,
            'normalized_AAC_padding_samples_removed': padding,
            'selected_clip_sha256': before, 'source_clips_unchanged': True}


def generate(episode, parts=None):
    if os.environ.get('ALLOW_PAID_GENERATION') != 'true':
        raise RuntimeError('Generation authorization is absent')
    numbers = parts or selected_parts(os.environ.get('INITIAL_PARTS', '')) or list(parts_for(episode))
    if parts is not None:
        raise ValueError('Repair and replacement generation are disabled')
    request = json.loads((ROOT / 'episode-request.json').read_text())
    if request['episode'] != episode or numbers != request['initial_parts']:
        raise ValueError('Generation differs from the fixed selected episode request')
    if numbers != sorted(set(numbers)) or request['maximum_initial_generations_per_selected_clip'] != 1:
        raise ValueError('Only one initial request per selected part is allowed')
    if request['maximum_credits_per_clip'] != 8 or request['maximum_selected_initial_credits'] != 8*len(numbers):
        raise ValueError('Selected budget differs from approved bounds')
    if any(n not in parts_for(episode) for n in numbers):
        raise ValueError('Selected part outside reviewed episode')
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
    from concurrent.futures import ThreadPoolExecutor, as_completed
    pool = ThreadPoolExecutor(max_workers=min(3, len(numbers)))
    futures = {pool.submit(generate_one, episode, n, packets[n]): n for n in numbers}
    states = []
    try:
        for future in as_completed(futures):
            states.append(future.result())
    except BaseException:
        for future in futures: future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        pool.shutdown(wait=True)
    states.sort(key=lambda state: state['part'])
    report = {'episode': episode, 'title': packets[numbers[0]]['title'], 'parts': states, 'tts_used': False, 'post_dubbing': False,
              'subtitles_and_corner_credits': 'Applied locally after actual native-speech review.'}
    if parts:
        report['reviewed_replacement_parts'] = numbers
    elif len(numbers) < 12:
        report['reviewed_initial_partial_parts'] = numbers
        report['assembly_deferred_until_all_initial_parts_exist'] = True
    else:
        report.update(assemble_native_exact_slots(work))
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

