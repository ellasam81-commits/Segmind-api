"""One explicitly requested second MiniMax H3 suspense trial, with a stable idempotency key."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import httpx
from jsonschema import Draft202012Validator
import produce

ROOT=Path(__file__).resolve().parent
DEST=ROOT/'h3-single-test'
STATE=DEST/'checkpoint'
MODEL='minimax/minimax-h3'


def payload():
    m=json.loads((ROOT/'episode.json').read_text())
    return {'prompt':(ROOT/'H3-PART01-SINGLE-BOARD-PROMPT.txt').read_text(),
            'reference':[produce.data_uri(ROOT/'boards/board-01-single.jpg')],
            'duration_seconds':15,'quality':'480p','aspect_ratio':'16:9',
            'generate_audio':True,'enhance_prompt':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    produce.unpack();DEST.mkdir(exist_ok=True);STATE.mkdir(exist_ok=True)
    import base64
    image_pack=ROOT/'boards/board-01-single.json'
    if image_pack.is_file():
        entry=json.loads(image_pack.read_text());data=base64.b64decode(entry['data'],validate=True)
        if hashlib.sha256(data).hexdigest()!=entry['sha256']:raise RuntimeError('Storyboard checksum mismatch')
        (ROOT/'boards/board-01-single.jpg').write_bytes(data)
    body=payload()
    if args.dry_run:
        model=json.loads((DEST/'minimax-h3-contract.json').read_text())
        Draft202012Validator(model['request_schemas']['video.general']).validate(body)
        print('Validated: MiniMax H3 / 480p / 15s / 1 nine-panel storyboard / one script line')
        return
    key=os.environ.get('PROTOFACE_API_KEY','').strip()
    if not key or os.environ.get('ALLOW_PAID_GENERATION')!='true':
        raise RuntimeError('Missing generation authorization or repository credential')
    with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=90,follow_redirects=False) as client:
        model=produce.api(client,'GET','/v1/models/'+MODEL)
        if not model.get('available'):raise RuntimeError('Requested MiniMax H3 is unavailable')
        Draft202012Validator(model['request_schemas']['video.general']).validate(body)
        (DEST/'minimax-h3-contract.json').write_text(json.dumps(model,ensure_ascii=False,indent=2))
        (DEST/'prompt.txt').write_text(body['prompt'])
        pricing=model['pricing']
        base=15*pricing['qualities']['480p']['credits_per_second']
        addon=next(x for x in pricing['add_ons'] if x['id']=='reference_image')['by_quality']['480p']
        predicted=base+max(0,1-addon.get('included',0))*addon['credits_each']
        if predicted>18:raise RuntimeError('Live price exceeds the disclosed 18-credit trial; no run submitted')
        print('Live price before submission:',predicted,'credits',flush=True)
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        request_key='ep01-h3-single-board-480p-first-v1-'+digest[:24]
        record=STATE/'run.json'
        state=json.loads(record.read_text()) if record.exists() else {'idempotency_key':request_key,'input_sha256':digest}
        if state['idempotency_key']!=request_key:raise RuntimeError('Resume the original inputs; no replacement submitted')
        if not state.get('run_id'):
            produce.save(record,state)
            created=produce.api(client,'POST','/v1/run/'+MODEL,headers={'Idempotency-Key':request_key},json=body)
            state.update(run_id=created['id'],status=created['status'],credit_estimate=created.get('credit_estimate'))
            produce.save(record,state)
            print('MiniMax H3 accepted:',state['run_id'],'estimate:',state['credit_estimate'],flush=True)
        end=time.monotonic()+2400
        while time.monotonic()<end:
            status=produce.api(client,'GET',f"/v1/runs/{state['run_id']}/status")
            state['status']=status['status'];produce.save(record,state)
            print('MiniMax H3:',state['status'],flush=True)
            if state['status'] in {'failed','canceled'}:
                raise RuntimeError('MiniMax H3 trial '+state['status']+'; no automatic replacement')
            if state['status']=='completed':
                result=produce.api(client,'GET',f"/v1/runs/{state['run_id']}")
                url=(result.get('video') or {}).get('url')
                if not url:url=next((o.get('file',{}).get('url') for o in result.get('outputs',[]) if o.get('modality')=='video'),None)
                if not url:raise RuntimeError('Completed trial has no video URL')
                produce.fetch_video(url,DEST/'episode01-part01-h3-single-board-native-480p.mp4')
                (DEST/'completion.json').write_text(json.dumps({'run_id':state['run_id'],'status':result['status'],'credits':result.get('credits')},indent=2))
                produce.summary('## MiniMax H3 第一段测试完成\n\n480p，15秒，一张九宫格分镜参考。请下载 artifact；原生语音需要逐句检查，不代表已保证台词或口型正确。')
                return
            time.sleep(10)
        raise TimeoutError('The accepted trial is still processing; preserve its run ID instead of submitting a replacement')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc).replace(os.environ.get('PROTOFACE_API_KEY') or '\x00','[REDACTED]'),flush=True)
        raise SystemExit(1)
