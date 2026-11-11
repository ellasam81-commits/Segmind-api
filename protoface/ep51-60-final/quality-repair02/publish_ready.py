"""Publish ONLY an ephemeral PUBLIC input key and an encrypted quote in the same repo."""
from pathlib import Path
import argparse,base64,json,os,re
import httpx

P=Path(__file__).resolve().parent

def main(ep,run,repo,branch):
    assert 51<=ep<=60 and re.fullmatch(r'[\w.-]+/[\w.-]+',repo)
    folder=P/f'transport-public/ep{ep:02}'
    ready=json.loads((folder/'ready.json').read_text())
    quote=json.loads((folder/'preflight.sealed.json').read_text())
    assert str(ready['run_id'])==str(run)and ready['episode']==ep
    assert ready['input_public_key_pem'].startswith('-----BEGIN PUBLIC KEY-----')
    assert quote['algorithm']=='RSA-OAEP-SHA256+AES-256-GCM'
    records={'ready.json':ready,'preflight.sealed.json':quote}
    with httpx.Client(base_url='https://api.github.com',headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','User-Agent':'ThirteenDoors-public-key-channel'},timeout=45)as client:
        for name,data in records.items():
            raw=json.dumps(data,separators=(',',':')).encode()
            assert len(raw)<30000 and b'PRIVATE KEY'not in raw and b'PROTOFACE_API_KEY'not in raw
            path=f'protoface/ep51-60-final/quality-repair02/public-ready/{run}/{name}'
            old=client.get(f'/repos/{repo}/contents/{path}',params={'ref':branch})
            if old.status_code==200:
                assert base64.b64decode(old.json()['content'])==raw,'Do not replace a different existing input channel'
                continue
            assert old.status_code==404,old.status_code
            response=client.put(f'/repos/{repo}/contents/{path}',json={'message':f'Publish nonsecret public input channel for existing run{run}','branch':branch,'content':base64.b64encode(raw).decode()})
            response.raise_for_status()
    print(f'Public input key and encrypted quote published for run{run}; no private key, provider key, script or media exported.',flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('episode',type=int);a.add_argument('run');a.add_argument('repository');a.add_argument('branch');x=a.parse_args();main(x.episode,x.run,x.repository,x.branch)
