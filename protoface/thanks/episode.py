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
reference = "https://raw.githubusercontent.com/ellasam81-commits/Segmind-api/" + os.environ["GITHUB_SHA"] + "/protoface/thanks/ticket-cast.jpg"
with httpx.Client(base_url="https://api.protoface.com", headers={"Authorization": "Bearer " + os.environ["PROTOFACE_API_KEY"]}, timeout=90) as client:
    def get(path):
        return proto.request(client, "GET", path)
    model = get("/v1/models/" + model_id)
    schema = model["request_schemas"]["video.general"]
    validator = Draft202012Validator(schema)
    for seconds in range(21, 6, -1):
        prompt = """A warm quiet 15-second portrait 3D animated thank-you scene. Use both reference figures exactly. Left is the chibi singer in black leather, sunglasses, auburn swept hair. Right is the ONE canonical yellow flame toy whose body and head are the same wide rounded pear with three blunt peaks, large raised WHITE oval eyes with BLUE oval pupils, thin black eyelashes, circular coral blush, mitten hands, plain rounded ivory shoes (no laces). Faithfully reproduce the simple mascot in the reference, no anime redesign. One simple action ONLY on a dark blue stage in a warm honey spotlight. At the start a young man steps toward her carrying a small bouquet of unmistakable YELLOW ROSES wrapped in cream paper with a golden ribbon. He kneels beside her, makes warm eye contact, gently extends the bouquet with both hands and says softly in a male Mandarin voice “谢谢你们，小炭火。” She looks up, takes the bouquet into both hands, then he releases it; she hugs it and says in an adorable bright feminine Mandarin voice “谢谢！” Hold their smiles in a two-shot. Natural pauses; only these two short lines. Animation of weight, hands, breathing, blink, smooth gentle camera. End with both faces visible and yellow roses between them. No other props, no cards, no cards falling, no tickets, no writing, no text, no numbers, no dialogue other than the two thank you lines. No duplicating bouquets."""
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
