"""Generic locations shared by local transport helpers and Actions workers."""
from pathlib import Path
import os
SCRIPT_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("TD_SERIES_ROOT", SCRIPT_ROOT.parent if SCRIPT_ROOT.name == "infra" else SCRIPT_ROOT)).resolve()
AAD_PREFIX = "ep21-25"
REMOTE_ROOT = "protoface/ep21-25"
EPISODES = tuple(range(21, 26))
PARTS = tuple(range(1, 13))
MODEL = "minimax/minimax-h3"
LOCAL_RETURN_PRIVATE_KEY = Path(os.environ.get("TD_RETURN_PRIVATE_KEY", "/workspace/thirteen-doors-ep01-c01/transport-private/return-private.pem"))
