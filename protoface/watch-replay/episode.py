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
        prompt = """A single cute 3D yellow flame mascot with large shiny blue eyes, hands, blush and white shoes in the provided reference, alone in a cozy dark teal study at a wooden desk at night, laptop and green floral tissue box, no people, no screen imagery. A clear visual comedy with three successive shots, no speech, no text, no music. 0-4s frontal view, mascot leans close to camera and carefully turns the open silver laptop away so only the silver BACK faces the viewer. 4-8s turns back to watch, raises a confident thumb. Two large tears roll down cheeks, thumb slowly folds down, dabs one cheek; mascot draws one tissue and starts to sob. 8-15s essential close side-profile shot: place open laptop keyboard directly under mascot's face. Crying mascot bends forward in a deep bow from the waist, hands holding tissue at chest far away from keys, its yellow FOREHEAD physically lands ON the flat black keys. SHOW CONTACT held half a second, key depresses, clearly audible single click on impact. HEAD bounces back up shocked, looks from keyboard to its own forehead, touches forehead with hand in realization. No injury. No printed text. Spend full second half on the forehead-to-keyboard contact and rebound. Angle hides the display, never show a drama shot or human or actor. Smooth 3D animated acting, gentle toy-like rendering."""
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
