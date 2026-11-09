"""Batch41–45 closed: all60 authorized initial clips accepted; no further paid requests."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent
AAD_PREFIX="ep41-45"
REMOTE_ROOT="protoface/ep41-45"
MODEL="minimax/minimax-h3"
PARTS=tuple(range(1,13))
PARTS_BY_EPISODE={}
EPISODES=()
INITIAL_CLIP_COUNT=0
INITIAL_CREDITS=0
TOTAL_APPROVED_CREDITS=480
MAX_PARALLEL_INITIAL_REQUESTS=0
AUTHORIZED_INPUT_SHA256={}
ALREADY_ACCEPTED_PARTS=((41, 1), (41, 2), (41, 3), (41, 4), (41, 5), (41, 6), (41, 7), (41, 8), (41, 9), (41, 10), (41, 11), (41, 12), (42, 1), (42, 2), (42, 3), (42, 4), (42, 5), (42, 6), (42, 7), (42, 8), (42, 9), (42, 10), (42, 11), (42, 12), (43, 1), (43, 2), (43, 3), (43, 4), (43, 5), (43, 6), (43, 7), (43, 8), (43, 9), (43, 10), (43, 11), (43, 12), (44, 1), (44, 2), (44, 3), (44, 4), (44, 5), (44, 6), (44, 7), (44, 8), (44, 9), (44, 10), (44, 11), (44, 12), (45, 1), (45, 2), (45, 3), (45, 4), (45, 5), (45, 6), (45, 7), (45, 8), (45, 9), (45, 10), (45, 11), (45, 12))
def parts_for(episode):
    raise ValueError("Approved batch completed; no unsubmitted initial clips remain")
LOCAL_RETURN_PRIVATE_KEY=Path(os.environ.get("TD_RETURN_PRIVATE_KEY","/workspace/thirteen-doors/next-batch-41-45/transport-private/return-private.pem"))
