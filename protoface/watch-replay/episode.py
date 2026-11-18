"""Generate this episode once, using a supported duration and native sound."""
import hashlib
import importlib.util
import json
import os
import time
from pathlib import Path

import httpx
from jsonschema import Draft202012Validator

spec = importlib.util.spec_from_file_location("proto", "protoface/thoo-hoo-hangbo/run.py")
proto = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proto)
model_id = proto.MODEL
out = Path("watch-output")
out.mkdir(exist_ok=True)
reference = "https://raw.githubusercontent.com/ellasam81-commits/Segmind-api/" + os.environ["GITHUB_SHA"] + "/protoface/watch-replay/reference.jpg"
with httpx.Client(base_url="https://api.protoface.com", headers={"Authorization": "Bearer " + os.environ["PROTOFACE_API_KEY"]}, timeout=90) as client:
    def get(path):
        return proto.request(client, "GET", path)
    model = get("/v1/models/" + model_id)
    schema = model["request_schemas"]["video.general"]
    validator = Draft202012Validator(schema)
    for seconds in range(21, 6, -1):
        prompt = """Vertical 9:16 polished 3D toy animation. The reference is four expressions of ONE yellow flame mascot T Hoo Hoo; animate only ONE. Big blue oval eyes, lashes, smooth yellow flame-shaped body, little white shoes. Cozy room at night, dark teal wall, warm wooden desk, box of tissues and open silver laptop. We face the mascot over the laptop BACK. Never show the screen, any reflections, actors, people, horses or the drama itself. Smooth expressive acting. One consistent original cute Mandarin voice. No music, captions or text. Opening: confidently turns laptop away from camera and addresses us. Says in Mandarin: “AI二创？你们看我，我看谢却山。” A distant horse whinny, hooves, wooden wheel creak FROM laptop. Mascot freezes, eyes fill with tears, draws tissue, sniffles sincerely. While sobbing its forehead accidentally taps the keyboard, click. EXACT SAME whinny plays again. Mascot jumps and bursts out “谁按的重播？！” A beat. Realizes, hugs whole tissue box and whispers “谢却山，等我擤完鼻子。” Finish with a funny nose blow. Synchronized clean Chinese voice, audible laptop effects. The joke is the accidental replay."""
        payload = dict(prompt=prompt, reference=[reference], duration_seconds=seconds, quality="480p", aspect_ratio="9:16", generate_audio=True, enhance_prompt=False)
        if len(model.get("operations", {})) > 1:
            payload["operation"] = "video.general"
        if validator.is_valid(payload):
            break
    else:
        raise RuntimeError("No compatible vertical request")
    cost = proto.price(model) + (seconds-7)*float(model["pricing"]["qualities"]["480p"]["credits_per_second"])
    print(f"One {seconds}s render, live estimate {cost:.2f} credits", flush=True)
    if model.get("available") is False or float(get("/v1/billing/quota").get("balance_credits",0)) < cost:
        raise RuntimeError("Unavailable or insufficient balance; no submission")
    identifier = "watch-replay-" + hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:32]
    job = proto.request(client,"POST","/v1/run/"+model_id,headers={"Idempotency-Key":identifier},json=payload)
    rid = job["id"]
    for _ in range(120):
        status = get("/v1/runs/"+rid+"/status")["status"]
        if status == "completed":
            break
        if status not in ("queued", "running"):
            raise RuntimeError("Provider status: "+status)
        time.sleep(10)
    else:
        raise RuntimeError("Provider timeout; no repeat submission")
    proto.download_video(get("/v1/runs/"+rid),out/"THooHoo_Replay.mp4")
