"""Fixed episode41 initial pilot: exactly two reviewed five-second requests."""
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parent
AAD_PREFIX="ep41-45"
REMOTE_ROOT="protoface/ep41-45"
EPISODES=(41,)
PARTS=(1,2)
MODEL="minimax/minimax-h3"
INITIAL_CLIP_COUNT=2
INITIAL_CREDITS=16
AUTHORIZED_INPUT_SHA256={'1': 'ec7b0caf1d193ce8aa7b423738c7bd94542b83d831868427acfe15bdc128feb9', '2': '27bd514fb94f00de1d4edd52819df5106f989625b834471d09b98335f56aad77'}
def parts_for(episode):
    if episode!=41:raise ValueError("Only episode41 pilot is authorized")
    return PARTS
LOCAL_RETURN_PRIVATE_KEY=Path(os.environ.get("TD_RETURN_PRIVATE_KEY","/workspace/thirteen-doors/next-batch-41-45/transport-private/return-private.pem"))
