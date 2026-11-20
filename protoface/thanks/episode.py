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
        prompt = """Portrait 3D animated 15s stage comedy, portrait concert stage midnight indigo, footlights, gold confetti, physically expressive original animation. Match the character board faithfully: left one chibi man with sunglasses leather jacket red brown quiff. Right ONE yellow soft vinyl flame mascot T Hoo Hoo, exactly reference sculpt with broad pear-shaped body, THREE round flame peaks, blue pupils in HUGE WHITE oval eyes with three eyelashes, red circular blush, yellow mitten hands, short legs chunky white shoes. Preserve sculpt. Start with tiny sneakers skidding: mascot hurries on stage hugging a wobbling stack of FOUR oversized metallic-gold concert tickets embossed with stars. She trips softly; cards fly up. 2-5 seconds medium shot, she catches three against her belly, the fourth sails toward camera. Male chibi singer catches that ticket neatly between two fingers. She says in cute feminine Mandarin “哎呀，还差一张！” 5-10 seconds he kneels to hand it back, says in warm original male Mandarin “接住啦！四张，都是小炭火一起攒的。” 10-15 seconds They turn to audience and bow together. She waves with one hand and says brightly “谢谢每一位小炭火！” A gold ticket sweeps across lens in final frame, transition to results. Accurate Chinese speech. No flowers, no text or printed words, no captions, no spectators visible; four simple embossed star tickets. Sound: sneakers squeak, flutter, soft chime. No human photorealism. Allow acting to dominate; never pan across a still image."""
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
