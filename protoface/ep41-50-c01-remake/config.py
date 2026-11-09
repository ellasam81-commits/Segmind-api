"""One new attempt per slot in the explicitly authorized41–50 C01 remake."""
from pathlib import Path
import json,os
MODULE_ROOT=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('TD_SERIES_ROOT',str(MODULE_ROOT)))
AAD_PREFIX='ep41-50-c01-remake'
REMOTE_ROOT='protoface/ep41-50-c01-remake'
MODEL='minimax/minimax-h3'
EPISODES=tuple(range(41,51))
PARTS=tuple(range(1,13))
INITIAL_CLIP_COUNT=120
INITIAL_CREDITS=960
TOTAL_APPROVED_CREDITS=960
AUTHORIZED_INPUT_SHA256=json.loads((MODULE_ROOT/'authorized-input-sha256.json').read_text())
def parts_for(episode):
    if episode not in EPISODES:raise ValueError('Episode outside explicit41–50 remake')
    return PARTS
