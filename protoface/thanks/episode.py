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
reference = "https://raw.githubusercontent.com/ellasam81-commits/Segmind-api/" + os.environ["GITHUB_SHA"] + "/protoface/thanks/reference.jpg"
with httpx.Client(base_url="https://api.protoface.com", headers={"Authorization": "Bearer " + os.environ["PROTOFACE_API_KEY"]}, timeout=90) as client:
    def get(path):
        return proto.request(client, "GET", path)
    model = get("/v1/models/" + model_id)
    schema = model["request_schemas"]["video.general"]
    validator = Draft202012Validator(schema)
    for seconds in range(21, 6, -1):
        prompt = """One continuous 15-second cinematic 3D chibi miniature stage comedy, portrait. Reference left image for the chibi male singer (auburn swept-back hair, black sunglasses and black leather stage outfit), reference right for the SAME single small female flame mascot (sunny yellow body, big oval blue eyes, blush, white shoes). Keep them both fully in frame. Real animated characters acting, not an animated poster. Midnight-blue stage with warm golden spotlights. At 0s she tiptoes toward the singer, hands hidden behind her back, the man hides a big bouquet of yellow roses behind his own back. At 3s they both reveal their surprise simultaneously: she presents a single tiny yellow rose, he presents his huge bouquet. Both blink, exchange looks and laugh! 5-9s the man crouches and really passes the bouquet into her arms. In a gentle original male Mandarin voice he says '谢谢你，也谢谢每一位小炭火。' 9-12s she hugs the flowers, face peeks out and in her own adorable bright female Mandarin voice replies '哎呀，花都比我高啦！' 12-15s she waves to the audience while he bows beside her. Synchronized natural Mandarin, soft room ambience, smooth movement. Exactly two characters, no text, no numbers, no graphic panels."""
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
