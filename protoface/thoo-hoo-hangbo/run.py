"""Independent, manual Protoface H3 minidrama. No scheduled/automatic paid calls."""
import hashlib,json,os,re,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from jsonschema import Draft202012Validator

ROOT=Path("protoface/thoo-hoo-hangbo")
OUT=Path("thoo-hoo-hangbo-output")
MODEL="minimax/minimax-h3"

def store(path,data):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
def summary(s):
 p=os.getenv("GITHUB_STEP_SUMMARY")
 if p:
  with open(p,"a",encoding="utf-8") as f:f.write(s+"\n\n")
def request(c,method,url,**kw):
 try:r=c.request(method,url,**kw)
 except httpx.RequestError as e:raise RuntimeError("Network uncertainty: re-run SAME GitHub run, do not create another paid request") from e
 if not r.is_success:raise RuntimeError("Protoface returned HTTP "+str(r.status_code)+"; no automatic retry")
 return r.json()
def price(model):
 try:
  p=model["pricing"]
  base=7*float(p["qualities"]["480p"]["credits_per_second"])
  ref=next(x for x in p["add_ons"] if x.get("id")=="reference_image")["by_quality"]["480p"]
  return base+max(0,1-int(ref.get("included",0)))*float(ref["credits_each"])
 except (KeyError,StopIteration,TypeError,ValueError) as e:
  raise RuntimeError("Live credits price missing: stopping before paid request") from e
def download_video(result,path):
 if path.exists() and path.stat().st_size>10000:return
 urls=[]
 if isinstance(result.get("video"),dict):urls.append(result["video"].get("url"))
 for x in result.get("outputs",[]):
  if x.get("modality")=="video" and isinstance(x.get("file"),dict):urls.append(x["file"].get("url"))
 u=next((x for x in urls if isinstance(x,str) and urlsplit(x).scheme=="https"),None)
 if not u:raise RuntimeError("Video completed but no HTTPS link; see result.json")
 with httpx.Client(follow_redirects=True,timeout=180) as d:
  with d.stream("GET",u) as r:
   r.raise_for_status()
   with path.open("wb") as f:
    for chunk in r.iter_bytes():f.write(chunk)
 if path.stat().st_size<10000:raise RuntimeError("Downloaded media incomplete")
def main():
 action=os.getenv("ACTION","inspect_model")
 if action not in ("check_connection","inspect_model","generate_range"):raise RuntimeError("Invalid action")
 key=os.getenv("PROTOFACE_API_KEY","").strip()
 if not key:raise RuntimeError("GitHub secret PROTOFACE_API_KEY missing")
 project=json.loads((ROOT/"scenes.json").read_text(encoding="utf-8"))
 scenes=project["scenes"]
 if len(scenes)!=6:raise RuntimeError("Manifest requires exactly six scenes")
 OUT.mkdir(exist_ok=True)
 with httpx.Client(base_url="https://api.protoface.com",headers={"Authorization":"Bearer "+key},timeout=60) as c:
  if action=="check_connection":
   request(c,"GET","/v1/models");summary("Protoface connection OK; zero paid video requests.");return
  model=request(c,"GET","/v1/models/"+MODEL)
  store(OUT/"model.json",model)
  if action=="inspect_model":
   summary("Inspected live H3 schema and pricing. Zero paid video requests.");return
  if os.getenv("CONFIRM_SPEND","").lower()!="true":raise RuntimeError("Explicit confirm_spend required")
  start=int(os.getenv("START_SCENE","1"));end=int(os.getenv("END_SCENE","1"))
  cap=float(os.getenv("MAX_TOTAL_CREDITS","0"))
  if not (1<=start<=end<=6) or cap<=0:raise RuntimeError("Invalid scene range or zero credit cap; no charge")
  if model.get("available") is False:raise RuntimeError("Model unavailable")
  schema=model.get("request_schemas",{}).get("video.general")
  if not isinstance(schema,dict):raise RuntimeError("H3 input schema missing")
  payloads={}
  for i in range(start,end+1):
   s=scenes[i-1]
   p={"prompt":project["common"]+"\nSINGLE SHOT: "+s["prompt"],"reference":project["reference"],
      "duration_seconds":7,"quality":"480p","aspect_ratio":"16:9","generate_audio":True,"enhance_prompt":False}
   if len(model.get("operations",{}))>1:p["operation"]="video.general"
   issues=list(Draft202012Validator(schema).iter_errors(p))
   if issues:raise RuntimeError("Scene "+str(i)+" invalid under live H3 schema: "+issues[0].message)
   payloads[i]=p
  estimate=(end-start+1)*price(model)
  if estimate>cap:raise RuntimeError(f"Estimated {estimate:.2f} credits exceeds user cap {cap:.2f}; no charge")
  quota=request(c,"GET","/v1/billing/quota")
  if float(quota.get("balance_credits",0))<estimate:raise RuntimeError("Not enough credits; no requests")
  summary(f"Authorized scene range {start}-{end}; estimated credits {estimate:.2f} (cap {cap:.2f}).")
  for i,p in payloads.items():
   folder=OUT/f"scene-{i:02d}";folder.mkdir(exist_ok=True)
   checkpoint=folder/"checkpoint.json"
   digest=hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest()[:20]
   state=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
   if state and state.get("digest")!=digest:raise RuntimeError("Checkpoint mismatch")
   if not state.get("id"):
    idem=f"hangbo-{os.environ['GITHUB_RUN_ID']}-{i}-{digest}"
    x=request(c,"POST","/v1/run/"+MODEL,headers={"Idempotency-Key":idem},json=p)
    rid=x.get("id","")
    if not re.fullmatch(r"run_[A-Za-z0-9_-]+",rid):raise RuntimeError("Invalid run ID; retry SAME run")
    state={"id":rid,"digest":digest}
    store(checkpoint,state);store(folder/"submitted.json",x)
   rid=state["id"]
   end_time=time.monotonic()+1200
   while time.monotonic()<end_time:
    st=request(c,"GET",f"/v1/runs/{rid}/status");store(folder/"status.json",st)
    if st.get("status") in ("completed","failed","canceled"):break
    if st.get("status") not in ("queued","running"):raise RuntimeError("Unexpected provider state")
    time.sleep(10)
   else:raise RuntimeError("Timed out. Re-run SAME workflow job; no new paid request")
   result=request(c,"GET",f"/v1/runs/{rid}");store(folder/"result.json",result)
   if result.get("status")!="completed":raise RuntimeError("Provider did not complete; no replacement request")
   download_video(result,OUT/f"scene-{i:02d}.mp4")
   summary(f"Scene {i} video downloaded. Provider ID: {rid}.")
  srt=[]
  for i in range(start,end+1):
   at=(i-start)*7
   srt.append(f"{i-start+1}\n00:00:{at:02d},200 --> 00:00:{at+6:02d},700\n{scenes[i-1]['sub']}\n")
  (OUT/"subtitles.srt").write_text("\n".join(srt),encoding="utf-8")
  if start==1 and end==6:
   clips=OUT/"clips.txt"
   clips.write_text("".join(f"file 'scene-{i:02d}.mp4'\n" for i in range(1,7)),encoding="utf-8")
   try:
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","concat","-safe","0",
                    "-i","clips.txt","-c","copy","hangbo_42s.mp4"],cwd=OUT,check=True)
    summary("All six parts joined: hangbo_42s.mp4; subtitles.srt included.")
   except Exception as e:
    summary("All six MP4 clips saved, but stitching failed; join them in CapCut with subtitles.srt.")
if __name__=="__main__":
 try:main()
 except Exception as e:
  key=os.getenv("PROTOFACE_API_KEY","")
  msg=str(e).replace(key,"[REDACTED]") if key else str(e)
  print("STOP:",msg,file=sys.stderr);summary("Stopped: "+msg);sys.exit(1)
