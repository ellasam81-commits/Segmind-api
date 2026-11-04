"""Generate the episode's reference-led shots with the user's Protoface secret."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time
import sys
from urllib.parse import urlsplit

import httpx
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]
STATE=ROOT/"checkpoint"
MODEL="minimax/minimax-h3"


def request(client,method,path,**kwargs):
    # No automatic POST retry; reuse this GitHub run's idempotency keys on rerun.
    response=client.request(method,path,**kwargs)
    if not response.is_success:
        try: code=response.json().get("error",{}).get("code","request_failed")
        except (ValueError,AttributeError): code="request_failed"
        raise RuntimeError(f"Protoface HTTP {response.status_code}: {code}")
    return response.json()


def save_state(path,data):
    temporary=path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data,indent=2))
    temporary.replace(path)


def summary(message):
    path=os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path,"a",encoding="utf-8") as out: out.write(message+"\n\n")


def generation_duration(schema,edit_duration):
    field=schema.get("properties",{}).get("duration_seconds",{})
    if "enum" in field:
        candidates=[x for x in field["enum"] if isinstance(x,(int,float)) and x>=edit_duration]
        if not candidates: raise ValueError("The model cannot supply this shot duration")
        return min(candidates)
    minimum=field.get("minimum",edit_duration)
    duration=math.ceil(max(edit_duration,minimum))
    if duration>field.get("maximum",duration): raise ValueError("Shot exceeds the model's maximum duration")
    return duration


def payload_for(shot,schema,quality,has_multiple_operations=False):
    props=schema.get("properties",{})
    required_fields={"first_frame","prompt","duration_seconds","quality","aspect_ratio"}
    if not required_fields.issubset(props):
        raise ValueError("MiniMax H3's input contract changed; expected image-to-video fields are missing. No runs submitted.")
    data=base64.b64encode((ROOT/shot["image"]).read_bytes()).decode()
    payload={"prompt":shot["generation_prompt"],"first_frame":"data:image/jpeg;base64,"+data,
             "duration_seconds":generation_duration(schema,shot["duration"]),
             "quality":quality,"aspect_ratio":"16:9"}
    if "generate_audio" in props: payload["generate_audio"]=False
    if has_multiple_operations: payload["operation"]="video.general"
    Draft202012Validator(schema).validate(payload)
    return payload


def idempotency_key(run,identifier,payload):
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:20]
    return f"drama-{run}-{identifier}-{digest}"


def output_url(body):
    video=body.get("video") or {}
    candidates=[video.get("url")]
    candidates.extend((item.get("file") or {}).get("url") for item in body.get("outputs",[])
                      if item.get("modality")=="video")
    for value in candidates:
        if not isinstance(value,str): continue
        p=urlsplit(value)
        if p.scheme=="https" and p.hostname and not p.username: return value
    raise ValueError("Completed run has no HTTPS video output")


def download_video(url,target):
    temporary=target.with_suffix(".part")
    # Do not send the Protoface API key to the media host.
    with httpx.Client(timeout=120,follow_redirects=True) as downloader:
        with downloader.stream("GET",url) as response:
            response.raise_for_status()
            with temporary.open("wb") as stream:
                for chunk in response.iter_bytes(): stream.write(chunk)
    check=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries",
                         "format=duration:stream=codec_type","-of","json",str(temporary)]))
    if not any(s.get("codec_type")=="video" for s in check.get("streams",[])):
        raise ValueError("Downloaded output does not contain a video stream")
    if float(check.get("format",{}).get("duration",0))<2:
        raise ValueError("Downloaded video is too short for a two-second shot")
    temporary.replace(target)


def one_shot(client,shot,payload,workflow_run):
    state_path=STATE/f"{shot['id']}.json"
    target=STATE/"clips"/f"{shot['id']}.mp4"
    key=idempotency_key(workflow_run,shot["id"],payload)
    state=json.loads(state_path.read_text()) if state_path.exists() else {"idempotency_key":key}
    if state.get("idempotency_key")!=key:
        raise ValueError("A checkpoint belongs to different inputs. Keep the same code when re-running a job.")
    if target.is_file() and state.get("status")=="completed": return target
    if not state.get("run_id"):
        save_state(state_path,state)
        created=request(client,"POST",f"/v1/run/{MODEL}",json=payload,headers={"Idempotency-Key":key})
        identifier=created.get("id","")
        if not re.fullmatch(r"run_[A-Za-z0-9_-]+",identifier): raise ValueError("Invalid run ID returned")
        state.update(run_id=identifier,status=created.get("status","queued"),credit_estimate=created.get("credit_estimate"))
        save_state(state_path,state)
        summary(f"{shot['id']}: `{identifier}`. Accepted estimate: `{json.dumps(state['credit_estimate'])}`")
    identifier=state["run_id"]
    print(f"{shot['id']}: {identifier}",flush=True)
    deadline=time.monotonic()+1500
    while time.monotonic()<deadline:
        status=request(client,"GET",f"/v1/runs/{identifier}/status")
        state["status"]=status.get("status")
        save_state(state_path,state)
        if state["status"] in {"failed","canceled"}:
            raise RuntimeError(f"{shot['id']} ended as {state['status']}; no replacement was submitted")
        if state["status"]=="completed":
            body=request(client,"GET",f"/v1/runs/{identifier}")
            if body.get("status")!="completed": raise RuntimeError("Run/status responses disagree")
            download_video(output_url(body),target)
            save_state(state_path,state)
            return target
        if state["status"] not in {"queued","running"}: raise RuntimeError("Unexpected run status")
        time.sleep(5)
    raise TimeoutError(f"Still waiting for {identifier}. Re-run the same GitHub run to resume; it was not canceled.")


def generate(first_only=False):
    if os.environ.get("PROTOFACE_CONFIRM_SPEND","").lower()!="true":
        raise RuntimeError("Generation requires the workflow's confirm_spend checkbox")
    key=os.environ.get("PROTOFACE_API_KEY","").strip()
    if not key: raise RuntimeError("Missing repository secret PROTOFACE_API_KEY")
    workflow_run=os.environ.get("GITHUB_RUN_ID")
    if not workflow_run: raise RuntimeError("Missing GITHUB_RUN_ID for idempotency")
    manifest=json.loads((ROOT/"production/episode04.json").read_text())
    shots=manifest["shots"][:1] if first_only else manifest["shots"]
    quality=os.environ.get("PROTOFACE_QUALITY","480p")
    STATE.mkdir(parents=True,exist_ok=True);(STATE/"clips").mkdir(exist_ok=True)
    with httpx.Client(base_url="https://api.protoface.com",timeout=90,
                      headers={"Authorization":f"Bearer {key}"},follow_redirects=False) as client:
        model=request(client,"GET",f"/v1/models/{MODEL}")
        if model.get("available") is False: raise RuntimeError("MiniMax H3 is unavailable")
        schema=model.get("request_schemas",{}).get("video.general")
        if not isinstance(schema,dict) or not schema: raise RuntimeError("Missing live video.general schema")
        payloads=[payload_for(s,schema,quality,len(model.get("operations",{}))>1) for s in shots]
        seconds=sum(p["duration_seconds"] for p in payloads)
        summary(f"## 第4集 · 作者 林爱丽\n\n{len(shots)} shots, {seconds} generated seconds at {quality}. "
                "Each reference-led shot is cut to 2 seconds in the edit. No dialogue voice track is included.")
        quota=request(client,"GET","/v1/billing/quota")
        if quota.get("balance_credits",0)<=0: raise RuntimeError("Protoface credit balance is empty")
        for sh,payload in zip(shots,payloads):
            one_shot(client,sh,payload,workflow_run)
    if first_only:
        summary("First shot ready in the checkpoint artifact. No other shots were submitted.")
    else:
        subprocess.run(["python",str(ROOT/"production/render.py"),"--generated-clips",str(STATE/"clips")],check=True)
        summary("## 成片已完成\n\nDownload **episode04-animated.mp4** in the episode artifact. "
                "It includes BGM, sound effects, bilingual subtitles, title, episode, and author credits; no dialogue dubbing.")


def check_contract():
    key=os.environ.get("PROTOFACE_API_KEY","").strip()
    if not key:
        print("No key configured; preview rendering does not require one.")
        return
    with httpx.Client(base_url="https://api.protoface.com",timeout=60,
                      headers={"Authorization":f"Bearer {key}"},follow_redirects=False) as client:
        model=request(client,"GET",f"/v1/models/{MODEL}")
    schema=model.get("request_schemas",{}).get("video.general",{})
    info={"id":model.get("id"),"available":model.get("available"),
          "operations":model.get("operations"),"request_schemas":model.get("request_schemas")}
    (ROOT/"output").mkdir(exist_ok=True)
    (ROOT/"output/live-model-contract.json").write_text(json.dumps(info,indent=2))
    print("Live MiniMax H3 input contract:",json.dumps(schema,ensure_ascii=False),flush=True)


if __name__=="__main__":
    try:
        if "--check-contract" in sys.argv: check_contract()
        else: generate(os.environ.get("PROTOFACE_MODE")=="generate_first_shot")
    except Exception as exc:
        message=str(exc).replace(os.environ.get("PROTOFACE_API_KEY") or "\x00","[REDACTED]")
        print(message,flush=True)
        raise SystemExit(1)
