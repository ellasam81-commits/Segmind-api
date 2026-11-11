import hashlib, json, os, time
from pathlib import Path
import httpx
from jsonschema import Draft202012Validator

ROOT=Path("protoface/qqmusic-anime-guide")
OUT=ROOT/"output"
MODEL="minimax/minimax-h3"
MAX_PER_PART=15.0
MAX_TOTAL=75.0

def walk_strings(x):
    if isinstance(x,str):
        yield x
    elif isinstance(x,dict):
        for v in x.values(): yield from walk_strings(v)
    elif isinstance(x,list):
        for v in x: yield from walk_strings(v)

def download_video(client, result, dest):
    urls=[s for s in walk_strings(result) if s.startswith(("https://","http://"))]
    for u in urls:
        try:
            with client.stream("GET",u,timeout=180,follow_redirects=True) as r:
                ct=(r.headers.get("content-type") or "").lower()
                if r.is_success and ("video" in ct or any(q in u.lower() for q in (".mp4",".mov",".webm"))):
                    with open(dest,"wb") as f:
                        for chunk in r.iter_bytes(): f.write(chunk)
                    if dest.stat().st_size>10000: return True
        except Exception:
            pass
    return False

def main():
    key=os.environ.get("PROTOFACE_API_KEY","").strip()
    if not key: raise RuntimeError("Missing PROTOFACE_API_KEY repository secret")
    req=json.loads((ROOT/"generation-request.json").read_text(encoding="utf-8"))
    assert len(req["parts"])==5 and float(req["max_total_credits"])<=MAX_TOTAL
    ref=req["reference"]
    OUT.mkdir(parents=True,exist_ok=True)
    with httpx.Client(base_url="https://api.protoface.com",headers={"Authorization":"Bearer "+key},timeout=60,follow_redirects=True) as client:
        def api(method,path,**kwargs):
            r=client.request(method,path,**kwargs)
            if not r.is_success:
                body=(r.text or "")[:1200]
                raise RuntimeError(f"Protoface HTTP {r.status_code}: {body}; no automatic resubmission")
            return r.json()
        model=api("GET","/v1/models/"+MODEL)
        schema=model.get("request_schemas",{}).get("video.general")
        if not schema or model.get("available") is False: raise RuntimeError("H3 unavailable or schema missing")
        quota=api("GET","/v1/billing/quota")
        balance=float(quota.get("balance_credits",0))
        spent_est=0.0
        for p in req["parts"]:
            part=int(p["part"])
            payload={
                "prompt":p["prompt"],"reference":[ref],"duration_seconds":12,
                "quality":"480p","aspect_ratio":"16:9","generate_audio":True,
                "enhance_prompt":False
            }
            if len(model.get("operations",{}))>1: payload["operation"]="video.general"
            Draft202012Validator(schema).validate(payload)
            pricing=model["pricing"]
            estimate=12*float(pricing["qualities"]["480p"]["credits_per_second"])
            rule=next(r for r in pricing["add_ons"] if r["id"]=="reference_image")["by_quality"]["480p"]
            estimate += max(0,1-int(rule.get("included",0)))*float(rule["credits_each"])
            if estimate>MAX_PER_PART or spent_est+estimate>float(req["max_total_credits"]):
                raise RuntimeError(f"Credit cap blocks part {part}: estimate {estimate}")
            if balance < spent_est+estimate: raise RuntimeError("Insufficient Protoface credits; nothing further submitted")
            digest=hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()[:24]
            idem=f'{req["request_id"]}-part{part}-{digest}'
            created=api("POST","/v1/run/"+MODEL,json=payload,headers={"Idempotency-Key":idem})
            rid=created["id"]; spent_est+=estimate
            (OUT/f"part-{part:02d}-submitted.json").write_text(json.dumps(created,ensure_ascii=False,indent=2))
            deadline=time.monotonic()+1500
            result=None
            while time.monotonic()<deadline:
                st=api("GET",f"/v1/runs/{rid}/status")
                (OUT/f"part-{part:02d}-status.json").write_text(json.dumps(st,ensure_ascii=False,indent=2))
                if st["status"] in ("completed","failed","canceled"):
                    result=api("GET",f"/v1/runs/{rid}")
                    (OUT/f"part-{part:02d}-result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2))
                    if st["status"]!="completed": raise RuntimeError(f"Part {part} {st['status']}; no replacement submitted")
                    break
                time.sleep(10)
            if result is None: raise RuntimeError(f"Part {part} polling timed out; no replacement submitted")
            if not download_video(client,result,OUT/f"part-{part:02d}.mp4"):
                raise RuntimeError(f"Part {part} completed but no downloadable video URL was found")
            print(f"part {part} completed; estimated {estimate} credits")
    print("All five parts completed within configured 75-credit ceiling.")

if __name__=="__main__":
    try: main()
    except Exception as e:
        key=os.environ.get("PROTOFACE_API_KEY","")
        msg=str(e).replace(key,"[REDACTED]") if key else str(e)
        print(msg); raise SystemExit(1)
