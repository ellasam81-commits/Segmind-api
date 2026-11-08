"""Read-only model/schema/price/quota check using the existing repository secret."""
from pathlib import Path
import json,os
import httpx
import private_transport as transport
from config import ROOT,AAD_PREFIX,MODEL
from packet_constraints import estimated_part
def main():
    key=os.environ.get("PROTOFACE_API_KEY","").strip()
    if not key: raise RuntimeError("Existing PROTOFACE_API_KEY repository secret is missing")
    with httpx.Client(base_url="https://api.protoface.com",headers={"Authorization":"Bearer "+key},timeout=60,follow_redirects=False) as client:
        data=[]
        for path in ["/v1/models/"+MODEL,"/v1/billing/quota"]:
            response=client.get(path)
            if not response.is_success: raise RuntimeError("Read-only provider HTTP"+str(response.status_code))
            data.append(response.json())
    model,quota=data
    price=estimated_part(model)
    result={"model":model,"quota":quota,"estimated_per_clip_credits":price,"requested_clips_per_episode":12,"episode41_estimated_credits":12*price,"episode41_funding_sufficient":quota.get("balance_credits",0)>=12*price,"provider_methods":["GET","GET"],"video_generation_submitted":False}
    run=os.environ["GITHUB_RUN_ID"]
    envelope=transport.seal(json.dumps(result).encode(),(ROOT/"return-public.pem").read_bytes(),AAD_PREFIX+"-price-v1:"+run)
    (ROOT/"preflight.sealed.json").write_text(json.dumps(envelope))
    print("Read-only connection/model/price check completed. Private results encrypted. No video generated.",flush=True)
if __name__=="__main__":
    try:main()
    except Exception as e:
        print(type(e).__name__+": "+str(e).replace(os.environ.get("PROTOFACE_API_KEY") or "\0","[REDACTED]"))
        raise SystemExit(1)
