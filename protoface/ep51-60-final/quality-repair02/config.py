from pathlib import Path
import json,os
MODULE_ROOT=Path(__file__).resolve().parent
ROOT=Path(os.environ.get('TD_SERIES_ROOT',str(MODULE_ROOT)))
AAD_PREFIX='ep51-60-final-quality-repair02'
REMOTE_ROOT='protoface/ep51-60-final/quality-repair02'
MODEL='minimax/minimax-h3'
EPISODES=(58,)
PARTS=(12,)
INITIAL_CLIP_COUNT=1
INITIAL_CREDITS=8
TOTAL_APPROVED_CREDITS=8
AUTHORIZED_INPUT_SHA256=json.loads((MODULE_ROOT/'authorized-input-sha256.json').read_text())
def parts_for(episode):
 if episode!=58:raise ValueError('Only confirmed58:12 audio defect authorized')
 return PARTS
