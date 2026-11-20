"""Prepare the starter through ComfyUI and render one Wan 3.0 tracking shot."""
import base64
import json
import os
import sys
import subprocess
import time
from pathlib import Path

import requests

workflow = {
    "1": {"class_type": "LoadImage", "inputs": {"image": "ink-gallop.jpg"}},
    "2": {
        "class_type": "ImageScale",
        "inputs": {"image": ["1", 0], "upscale_method": "lanczos", "width": 1280, "height": 720, "crop": "center"},
    },
    "3": {"class_type": "SaveImage", "inputs": {"images": ["2", 0], "filename_prefix": "wan-starter"}},
}

if sys.argv[1] == "prepare":
    local = "http://127.0.0.1:8188"
    for _ in range(100):
        try:
            if requests.get(local + "/system_stats", timeout=2).ok:
                break
        except requests.ConnectionError:
            pass
        time.sleep(2)
    graph_path = Path("ink-starter-workflow.json")
    graph_path.write_text(json.dumps(workflow))
    subprocess.run(
        ["comfy", "run", "--where", "local", "--host", "127.0.0.1", "--port", "8188",
         "--workflow", str(graph_path), "--wait"],
        check=True,
    )
    frames = sorted(Path("ComfyUI/output").glob("wan-starter*.png"))
    if len(frames) != 1:
        raise RuntimeError("Expected one prepared starter from ComfyUI CLI")
    Path("starter.png").write_bytes(frames[0].read_bytes())
    sys.exit()

from segmind import SegmindClient

frame = base64.b64encode(Path("starter.png").read_bytes()).decode("ascii")
uploaded = requests.post(
    "https://workflows-api.segmind.com/upload-asset",
    headers={"x-api-key": os.environ["SEGMIND_API_KEY"], "accept": "application/json, text/plain, */*"},
    json={"data_urls": ["data:image/png;base64," + frame]},
    timeout=90,
)
uploaded.raise_for_status()
first_frame = uploaded.json()["file_urls"][0]
prompt = (
    "One uninterrupted, side-on tracking shot of ONE clean equestrian leap. Same ordinary fictional anime face, "
    "black-silver armor and silver half mask as the artwork. Show the whole horse and all hooves. "
    "In the first second collect into the approach. A shallow ink-dark stream crosses the path. "
    "The hind legs compress and drive off the near bank; the horse and rider leap from left to right "
    "over the water ONCE. At the apex forelegs fold under the chest and hind legs trail, then tuck. "
    "The rider rises slightly in the stirrups, folds forward over the neck and keeps the reins soft. "
    "Extend the forelegs, land forefeet first on the far bank around 3.1s, then hind feet. "
    "The camera tracks level and wide, with a continuous visible arc and clear air beneath all four hooves. "
    "Hold the landing long enough to see contact. On contact, a black ink splash blooms under the hoof "
    "and rises diagonally toward the lens, calligraphic bristles and ink bleeding on paper. "
    "High ponytail and cape stream left. Restrained original anime eyes, no identifiable real person's face. "
    "Keep pale mountains, charcoal line work and the lone red flag. Audio: approach hoofbeats, a hush "
    "during suspension, a firm wet hoof landing and short brush swish. No speech or music."
)
payload = {
    "image": first_frame, "prompt": prompt, "duration": 4, "resolution": "480P",
    "aspect_ratio": "16:9", "audio": True, "prompt_extend": False, "watermark": False,
    "negative_prompt": "repeated jumping, endless gallop, hidden landing, static horse, sliding feet, floating horse, duplicate legs, drifting mask, new rider, camera cuts, captions, photorealism",
}
output_dir = Path("result")
output_dir.mkdir(exist_ok=True)
client = SegmindClient()
job = client.submit_async("wan3.0-video", **payload)
(output_dir / "request-id.txt").write_text(job.request_id + "\n")
print("Segmind accepted the shot.", flush=True)
result = job.wait(timeout=1500, interval=5)
def output_urls(value):
    if isinstance(value, str) and value.startswith("https://"):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from output_urls(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from output_urls(item)
for url in output_urls(result.get("output", result)):
    response = requests.get(url, timeout=100)
    response.raise_for_status()
    if response.content[4:8] == b"ftyp":
        (output_dir / "Xie_Queshan_Ink_Gallop_Wan3.mp4").write_bytes(response.content)
        break
else:
    raise RuntimeError("The completed request returned no MP4")
