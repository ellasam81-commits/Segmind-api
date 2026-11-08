"""Episode41–45 native480p production;12 five-second, three-shot boards per episode."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent
AAD_PREFIX="ep41-45"
REMOTE_ROOT="protoface/ep41-45"
EPISODES=tuple(range(41,46))
PARTS=tuple(range(1,13))
MODEL="minimax/minimax-h3"
def parts_for(episode):
    if episode not in EPISODES: raise ValueError("Episode outside requested batch")
    return PARTS
INITIAL_CLIP_COUNT=60
INITIAL_CREDITS=480
LOCAL_RETURN_PRIVATE_KEY=Path(os.environ.get("TD_RETURN_PRIVATE_KEY","/workspace/thirteen-doors/next-batch-41-45/transport-private/return-private.pem"))
