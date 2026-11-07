"""Generic locations shared by local transport helpers and Actions workers."""
from pathlib import Path
import os
SCRIPT_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("TD_SERIES_ROOT", SCRIPT_ROOT.parent if SCRIPT_ROOT.name == "infra" else SCRIPT_ROOT)).resolve()
AAD_PREFIX = "ep36-40"
REMOTE_ROOT = "protoface/ep36-40"
EPISODES = tuple(range(36, 41))
PARTS = tuple(range(1, 17))

def parts_for(episode):
    if episode not in EPISODES:
        raise ValueError("Episode outside reviewed batch")
    return tuple(range(1, 17 if episode == 37 else 13))

INITIAL_CLIP_COUNT = sum(len(parts_for(ep)) for ep in EPISODES)
INITIAL_CREDITS = INITIAL_CLIP_COUNT * 8
MODEL = "minimax/minimax-h3"
LOCAL_RETURN_PRIVATE_KEY = Path(os.environ.get("TD_RETURN_PRIVATE_KEY", "/workspace/thirteen-doors-ep01-c01/transport-private/return-private.pem"))
