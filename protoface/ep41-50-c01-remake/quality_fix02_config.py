"""One part5 repair attempt only; original120-slot initial worker remains unchanged."""
from pathlib import Path
import os,json
MODULE_ROOT=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('TD_SERIES_ROOT',str(MODULE_ROOT)))
AAD_PREFIX='ep41-50-c01-quality-fix02'
REMOTE_ROOT='protoface/ep41-50-c01-remake/quality-fix02'
MODEL='minimax/minimax-h3'
EPISODES=(41,)
PARTS=(5,)
INITIAL_CLIP_COUNT=1
INITIAL_CREDITS=8
AUTHORIZED_INPUT_SHA256=json.loads((MODULE_ROOT/'quality-fix02-input-sha256.json').read_text())
ORIGINAL_RUNS=json.loads((MODULE_ROOT/'quality-fix02-original-runs.json').read_text())
REPAIR_ID='c01-native-part5-fix02'
def parts_for(episode):
    if episode!=41:raise ValueError('Repair scope is only episode41 part5')
    return PARTS
