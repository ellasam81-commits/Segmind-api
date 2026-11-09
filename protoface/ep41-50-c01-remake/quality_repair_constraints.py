"""Offline, non-billable constraints used before encryption and before submission."""
import base64
import hashlib
import math
from decimal import Decimal, InvalidOperation
from quality_repair_config import EPISODES, PARTS, parts_for, INITIAL_CLIP_COUNT, INITIAL_CREDITS, AUTHORIZED_INPUT_SHA256

PER_CLIP_CREDITS = Decimal('8')


def decimal(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Invalid price') from None
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid price')
    return result


def estimated_part(model, packet=None):
    """Price exactly one reference image; reject live quotes above eight credits."""
    price = model['pricing']
    value = 5 * decimal(price['qualities']['480p']['credits_per_second'])
    rule = next(x for x in price['add_ons'] if x['id'] == 'reference_image')['by_quality']['480p']
    included = decimal(rule.get('included', 0))
    value += max(Decimal(0), 1 - included) * decimal(rule['credits_each'])
    limit = decimal((packet or {}).get('review_budget_credits', 8))
    if limit != PER_CLIP_CREDITS or value > limit:
        raise ValueError('Live quote exceeds the reviewed eight-credit limit; no submission')
    return float(value)


def payload(packet):
    if packet.get('extra_references') or any(packet.get(k) for k in ('first_frame', 'last_frame', 'reference_video', 'audio', 'speech_guide')):
        raise ValueError('Exactly one three-panel reference image is authorized; other media roles are disabled')
    return {
        'prompt': packet['prompt'],
        'reference': ['data:image/jpeg;base64,' + packet['image']['data']],
        'duration_seconds': 5, 'quality': '480p', 'aspect_ratio': '16:9',
        'generate_audio': True, 'enhance_prompt': False,
    }


def input_signature(packet):
    import json
    return hashlib.sha256(json.dumps(payload(packet), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def request_key(packet):
    signature = input_signature(packet)
    suffix = ''
    if packet.get('request_kind') == 'repair':
        request_id = packet.get('repair_request_id', '')
        if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
            raise ValueError('Reviewed repair identity is missing')
        original = packet.get('repair_authorization', {}).get('original_run_id')
        if not isinstance(original, str) or not original.strip():
            raise ValueError('Repair must identify the original accepted run')
        # Bound one additional generation to the original run, independent of
        # manifest ID or edited prompt. Re-dispatching cannot create another
        # paid take for that same original clip.
        return f'thirteen-ep41-50-c01-remake-three5-v1-ep{packet["episode"]:02}-p{packet["part"]:02}-repair-' + hashlib.sha256(original.encode()).hexdigest()[:24]
    return f'thirteen-ep41-50-c01-remake-three5-v1-ep{packet["episode"]:02}-p{packet["part"]:02}{suffix}-' + signature[:24]


def validate_packet(packet, episode=None, part=None):
    if packet.get('episode') not in EPISODES or packet.get('part') not in parts_for(packet['episode']):
        raise ValueError('Packet identity outside the authorized batch')
    if episode is not None and packet['episode'] != episode or part is not None and packet['part'] != part:
        raise ValueError('Private input identity mismatch')
    if not isinstance(packet.get('prompt'), str) or not packet['prompt'].strip():
        raise ValueError('Private generation prompt is missing')
    if packet.get('enhance_prompt', False) is not False:
        raise ValueError('Prompt enhancement would change reviewed instructions')
    if packet.get('review_budget_credits') != 8:
        raise ValueError('Packet must declare the eight-credit attempt cap')
    panels = packet.get('panels')
    if not isinstance(panels, list) or len(panels) != 3 or any(not p for p in panels):
        raise ValueError('Every input must contain exactly three reviewed panels')
    windows = packet.get('shot_windows')
    if not isinstance(windows, list) or len(windows) != 3:
        raise ValueError('Three explicit shot windows are required')
    previous = 0.0
    for window in windows:
        if not isinstance(window, (list, tuple)) or len(window) != 2:
            raise ValueError('Invalid shot timing')
        start, end = window
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in (start, end)):
            raise ValueError('Invalid shot timing')
        if abs(start - previous) > .00001 or end <= start or end > 5:
            raise ValueError('Shot windows must continuously cover five seconds')
        previous = end
    if abs(previous - 5) > .00001:
        raise ValueError('Three shots must sum to five seconds')
    metadata = packet.get('metadata', {})
    for key, expected in {'native_audio': True, 'post_dubbing': False, 'duration_seconds': 5, 'panels_per_image': 3}.items():
        if metadata.get(key) != expected:
            raise ValueError('Packet production format mismatch')
    image = packet.get('image', {})
    try:
        data = base64.b64decode(image['data'], validate=True)
    except Exception:
        raise ValueError('Invalid reference image encoding') from None
    if not data.startswith(b'\xff\xd8\xff') or hashlib.sha256(data).hexdigest() != image.get('sha256'):
        raise ValueError('Reference image checksum or format mismatch')
    review = packet.get('board_review', {})
    if review.get('state') != 'visually_reviewed' or review.get('source_sha256') != image.get('source_sha256'):
        raise ValueError('Reference image has not passed a matching human visual review')
    dialogue = packet.get('dialogue')
    if not isinstance(dialogue, list):
        raise ValueError('Explicit dialogue list is required, including silent clips')
    for utterance in dialogue:
        if not isinstance(utterance, dict) or any(not utterance.get(k) for k in ('speaker', 'source', 'text')):
            raise ValueError('Every utterance needs its original text, speaker and voice source')
        if not any(utterance.get(k) for k in ('voice', 'voice_description', 'voice_id')):
            raise ValueError('Every utterance needs an explicit voice identity')
        if not any(utterance.get(k) for k in ('tone', 'performance', 'delivery')):
            raise ValueError('Every utterance needs an explicit delivery direction')
        start, end = utterance.get('start'), utterance.get('end')
        if not all(isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= 5:
            raise ValueError('Dialogue must have a natural assigned time within the five-second clip')
    kind = packet.get('request_kind', 'initial')
    if kind != 'repair':
        raise ValueError('Unknown generation request kind')
    if kind == 'repair':
        authorization = packet.get('repair_authorization', {})
        for field in ('confirmed_defect', 'free_or_picture_repair_insufficient', 'no_consecutive_attempts'):
            if authorization.get(field) is not True:
                raise ValueError('Paid fallback needs confirmed defect and prior free/picture-repair diagnosis')
        if authorization.get('maximum_additional_generations') != 1 or not authorization.get('original_run_id'):
            raise ValueError('Only one additional generation for the reviewed original is authorized')
    from quality_repair_config import ORIGINAL_RUNS, REPAIR_ID
    slot=f"{packet['episode']}:{packet['part']}"
    if packet.get('repair_request_id')!=REPAIR_ID or authorization['original_run_id']!=ORIGINAL_RUNS.get(slot):
        raise ValueError('Repair is not one of the two explicitly bounded original runs')
    if len(ORIGINAL_RUNS)!=2 or len(AUTHORIZED_INPUT_SHA256)>2:
        raise ValueError('Repair batch exceeds its two-attempt sixteen-credit cap')
    if input_signature(packet) != AUTHORIZED_INPUT_SHA256.get(f"{packet['episode']}:{packet['part']}"):
        raise ValueError('Input differs from the exact approved remaining payload')
    payload(packet)
    request_key(packet)
    state = packet.get('resume_state')
    if state:
        if state.get('idempotency_key') != request_key(packet) or state.get('input_sha256') != input_signature(packet):
            raise ValueError('Resume checkpoint does not match the exact reviewed request')
    return packet

