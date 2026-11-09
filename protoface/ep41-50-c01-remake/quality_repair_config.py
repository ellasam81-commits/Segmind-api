"""Two repair attempts only; original120-slot initial worker remains unchanged."""
from pathlib import Path
import os,json
MODULE_ROOT=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('TD_SERIES_ROOT',str(MODULE_ROOT)))
AAD_PREFIX='ep41-50-c01-quality-fix01'
REMOTE_ROOT='protoface/ep41-50-c01-remake/quality-fix01'
MODEL='minimax/minimax-h3'
EPISODES=(41,)
PARTS=(2,4)
INITIAL_CLIP_COUNT=2
INITIAL_CREDITS=16
AUTHORIZED_INPUT_SHA256=json.loads((MODULE_ROOT/'quality-repair-input-sha256.json').read_text())
ORIGINAL_RUNS=json.loads((MODULE_ROOT/'quality-repair-original-runs.json').read_text())
REPAIR_ID='c01-native-first4-fix01'
def parts_for(episode):
    if episode!=41:raise ValueError('Repair scope is only episode41 parts2 and4')
    return PARTS
