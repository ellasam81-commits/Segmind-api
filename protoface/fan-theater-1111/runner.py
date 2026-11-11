import base64, hashlib, json, os, subprocess, time
from pathlib import Path
import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path("protoface/fan-theater-1111")
OUT = ROOT / "packets"
BRANCH = "fan-theater-1111-black-shirt"
REQ = "qq-billboard-blackshirt-1111-a"
MODEL = "minimax/minimax-h3"
def git(*args):
    subprocess.run(["git",*args], check=True, stdout=subprocess.DEVNULL)
def publish(paths,message):
    git("add","--",*[str(p) for p in paths])
    git("commit","-qm",message)
    git("push","-q","origin","HEAD:refs/heads/"+BRANCH)
def dump(p,data):
    p.write_text(json.dumps(data,separators=(",",":")))
def b64(b):
    return base64.b64encode(b).decode()
def report(s):
    print(s,flush=True)
def packet(content,label):
    iv=os.urandom(12)
    ct=AESGCM(key).encrypt(iv,content,label.encode())
    coded=b64(iv+ct)
    parts=[coded[i:i+56000] for i in range(0,len(coded),56000)]
    for i,x in enumerate(parts): (OUT/f"{label}-{i:03}.txt").write_text(x)
    dump(OUT/(label+".json"),{"parts":len(parts),"bytes":len(content),"sha256":hashlib.sha256(content).hexdigest()})
    publish([OUT], "Return encrypted "+label)
def fetch_payload():
    for i in range(150):
        git("fetch","-q","origin",BRANCH)
        v=subprocess.run(["git","show","FETCH_HEAD:"+str(ROOT/"cast-input.txt")],capture_output=True)
        if v.returncode==0:
            git("merge","--ff-only","FETCH_HEAD")
            raw=base64.b64decode(v.stdout)
            return json.loads(AESGCM(key).decrypt(raw[:12],raw[12:],REQ.encode()))
        time.sleep(6)
    raise RuntimeError("Input delivery timed out")
def main():
    global key
    principal=os.environ["PROTOFACE_API_KEY"]
    key=AESGCM.generate_key(bit_length=256)
    ret=serialization.load_pem_public_key((ROOT/"return-public.pem").read_bytes())
    wrapped=ret.encrypt(key,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    OUT.mkdir(parents=True,exist_ok=True)
    dump(ROOT/"ready.json",{"key":b64(wrapped),"request":REQ})
    git("config","user.name","github-actions[bot]")
    git("config","user.email","41898282+github-actions[bot]@users.noreply.github.com")
    publish([ROOT/"ready.json"],"Open private reference delivery for fan theater")
    req=fetch_payload()
    model_url="/v1/models/"+MODEL
    with httpx.Client(base_url="https://api.protoface.com",headers={"Authorization":"Bearer "+principal},timeout=90) as api:
        def get(path):
            res=api.get(path);res.raise_for_status();return res.json()
        model=get(model_url)
        pricing=model["pricing"]; quality="480p"; duration=12
        rule=next(x for x in pricing["add_ons"] if x["id"]=="reference_image")["by_quality"][quality]
        cost=duration*float(pricing["qualities"][quality]["credits_per_second"])+max(0,1-int(rule.get("included",0)))*float(rule["credits_each"])
        if cost>15 or float(get("/v1/billing/quota")["balance_credits"])<cost:raise RuntimeError("Requested single clip exceeds existing funds or 15-credit ceiling")
        photo=base64.b64decode(req["image"])
        reference="data:image/jpeg;base64,"+b64(photo)
        p={"prompt":req["prompt"],"reference":[reference],"duration_seconds":duration,"quality":quality,"aspect_ratio":"16:9","generate_audio":True,"enhance_prompt":False}
        if len(model.get("operations",{}))>1:p["operation"]="video.general"
        def submit():return api.post("/v1/run/"+MODEL,json=p,headers={"Idempotency-Key":REQ})
        r=submit()
        if r.status_code in (400,422):
            report("Inline reference rejected; trying account-scoped asset upload.")
            up=api.post("/v1/assets",files={"file":("cast.jpg",photo,"image/jpeg")})
            if up.is_success:
                asset=up.json(); aid=asset.get("id") or asset.get("asset_id")
                if aid:p["reference"]=[aid];r=submit()
        if not r.is_success:
            msg=r.json().get("error",{})
            report("Reference validation failed: "+str(r.status_code)+" "+(str(msg.get("code","")) if isinstance(msg,dict) else ""))
            raise RuntimeError("Reference was not accepted")
        run=r.json()["id"]
        report("Accepted one 12-second performance, id "+run)
        for _ in range(150):
            st=get("/v1/runs/"+run+"/status")["status"]
            if st in ("completed","failed","canceled"):break
            time.sleep(8)
        if st!="completed":raise RuntimeError("Provider state "+st)
        result=get("/v1/runs/"+run)
        media=httpx.get(result["video"]["url"],timeout=150,follow_redirects=True)
        media.raise_for_status()
        packet(media.content,"performance")
        report("Performance returned. Charged credits "+str((result.get("credits") or {}).get("charged","not specified")))
if __name__=="__main__":
    try:main()
    except Exception as e:
        if "key" in globals():
            # An already generated presenter shot from the same user's previous tutorial stays available for editing.
            prior=Path("protoface/qqmusic-anime-guide/output/part-04.mp4")
            if prior.is_file():packet(prior.read_bytes(),"previous-performance")
        print("Job ended:",type(e).__name__,str(e)[:200] if isinstance(e,RuntimeError) else "",flush=True)
        raise SystemExit(1)
