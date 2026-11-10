"""One part5 repair attempt only; original120-slot initial worker remains unchanged."""
from pathlib import Path
import os,json
MODULE_ROOT=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('TD_SERIES_ROOT',str(MODULE_ROOT)))
AAD_PREFIX='ep41-50-c01-quality-fix04'
REMOTE_ROOT='protoface/ep41-50-c01-remake/quality-fix04'
MODEL='minimax/minimax-h3'
EPISODES=(48,)
PARTS=(8,)
INITIAL_CLIP_COUNT=1
INITIAL_CREDITS=8
AUTHORIZED_INPUT_SHA256=json.loads((MODULE_ROOT/'quality-fix04-input-sha256.json').read_text())
ORIGINAL_RUNS=json.loads((MODULE_ROOT/'quality-fix04-original-runs.json').read_text())
REPAIR_ID='c01-ep48-p08-native-date-fix04'
def parts_for(episode):
    if episode!=48:raise ValueError('Repair scope is only episode48 part8')
    return PARTS
