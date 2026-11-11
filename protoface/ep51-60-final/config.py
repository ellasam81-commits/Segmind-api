"""One new attempt per slot in the explicitly authorized51–60 final batch."""
from pathlib import Path
import json,os
MODULE_ROOT=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('TD_SERIES_ROOT',str(MODULE_ROOT)))
AAD_PREFIX='ep51-60-final'
REMOTE_ROOT='protoface/ep51-60-final'
MODEL='minimax/minimax-h3'
EPISODES=tuple(range(51,61))
PARTS=tuple(range(1,13))
INITIAL_CLIP_COUNT=120
INITIAL_CREDITS=960
TOTAL_APPROVED_CREDITS=960
AUTHORIZED_INPUT_SHA256=json.loads((MODULE_ROOT/'authorized-input-sha256.json').read_text())
def parts_for(episode):
    if episode not in EPISODES:raise ValueError('Episode outside explicit51–60 final batch')
    return PARTS
