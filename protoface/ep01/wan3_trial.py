"""One explicitly requested Wan 3.0 trial, with a stable idempotency key."""
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
DEST=ROOT/'wan3'
STATE=DEST/'checkpoint'
MODEL='alibaba/wan-3.0'


def payload():
    m=json.loads((ROOT/'episode.json').read_text())
    p=json.loads((ROOT/'shot-directions.json').read_text())['parts'][0]
    lines=[
      '根据按顺序给出的9张独立剧情参考图，制作15秒、16:9横版、二维动漫恐怖悬疑视频。每张参考单独铺满画面，严格按1至9顺序硬切，不出现拼贴、编号、标题栏、说明栏或角色参考表。',
      '严格保留相同人物脸型、黑发、黑色长外套、高领毛衣、棕色斜挎包、场景、镜头角度和物件数量，不镜像，不改左右手。只有男主沈照夜一个人。不增加人物、鬼影、跳吓或支线。',
      '剧情因果：收到无寄件人的信封→取出一份失踪案卷→发现案卷地址→搜索地址但无结果→找旧地图。所有动作只按参考图做，轻微自然运镜、克制真实表情。',
      '声音白名单：整段只有一句男主对白，4.5—6.0秒说“青槐里十三号。”，低沉、清楚、冷静地轻声读出一次。此时画面是案卷特写，说话人是画外的沈照夜本人，不能变成解说旁白；不显示新的说话人。',
      '其余所有时段完全无对白，不重复地址，不读纸面其他文字、动作说明、position、语气、编号或时间。男声保持标准普通话，禁止女声、电话声、旁白、音乐、字幕。道具文字可按图保留，不能把字幕叠在视频上。',
      '安静与细微音效形成悬疑：只用纸张、呼吸、键盘和房间低鸣；本段没有敲门声、鬼叫或大声冲击。'
    ]
    for s in p['panels']:
        lines.extend([
          f"【镜头{s['number']}｜{s['start']:g}—{s['end']:g}秒｜对应参考图{s['number']}】",
          f"台词：{s['dialogue']}。说话人：{s['speaker']}；{s['audio_source']}。",
          f"动作：{s['action']}",f"表情：{s['expression']}",
          f"Position（位置、朝向、左右手）：{s['position']}",
          f"语气：{s['delivery']}",f"音效：{s['sfx']}"
        ])
    return {'operation':'video.reference','prompt':'\n'.join(lines),
            'reference_images':[produce.data_uri(ROOT/p['image']) for p in m['parts'][0]['panels']],
            'duration':15,'resolution':'480p','aspect_ratio':'16:9',
            'enable_audio':True,'enable_prompt_expansion':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    produce.unpack();DEST.mkdir(exist_ok=True);STATE.mkdir(exist_ok=True)
    body=payload()
    if args.dry_run:
        model=json.loads((DEST/'wan3-contract.json').read_text())
        Draft202012Validator(model['request_schemas']['video.reference']).validate(body)
        print('Validated: Wan 3.0 / 480p / 15s / 9 separate frames / one script line')
        return
    key=os.environ.get('PROTOFACE_API_KEY','').strip()
    if not key or os.environ.get('ALLOW_PAID_GENERATION')!='true':
        raise RuntimeError('Missing generation authorization or repository credential')
    with httpx.Client(base_url='https://api.protoface.com',headers={'Authorization':'Bearer '+key},timeout=90,follow_redirects=False) as client:
        model=produce.api(client,'GET','/v1/models/'+MODEL)
        if not model.get('available'):raise RuntimeError('Requested Wan 3.0 is unavailable')
        Draft202012Validator(model['request_schemas']['video.reference']).validate(body)
        (DEST/'wan3-contract.json').write_text(json.dumps(model,ensure_ascii=False,indent=2))
        (DEST/'prompt.txt').write_text(body['prompt'])
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        request_key='ep01-wan3-480p-first-v1-'+digest[:24]
        record=STATE/'run.json'
        state=json.loads(record.read_text()) if record.exists() else {'idempotency_key':request_key,'input_sha256':digest}
        if state['idempotency_key']!=request_key:raise RuntimeError('Resume the original inputs; no replacement submitted')
        if not state.get('run_id'):
            produce.save(record,state)
            created=produce.api(client,'POST','/v1/run/'+MODEL,headers={'Idempotency-Key':request_key},json=body)
            state.update(run_id=created['id'],status=created['status'],credit_estimate=created.get('credit_estimate'))
            produce.save(record,state)
            print('Wan 3.0 accepted:',state['run_id'],'estimate:',state['credit_estimate'],flush=True)
        end=time.monotonic()+2400
        while time.monotonic()<end:
            status=produce.api(client,'GET',f"/v1/runs/{state['run_id']}/status")
            state['status']=status['status'];produce.save(record,state)
            print('Wan 3.0:',state['status'],flush=True)
            if state['status'] in {'failed','canceled'}:
                raise RuntimeError('Wan 3.0 trial '+state['status']+'; no automatic replacement')
            if state['status']=='completed':
                result=produce.api(client,'GET',f"/v1/runs/{state['run_id']}")
                url=(result.get('video') or {}).get('url')
                if not url:url=next((o.get('file',{}).get('url') for o in result.get('outputs',[]) if o.get('modality')=='video'),None)
                if not url:raise RuntimeError('Completed trial has no video URL')
                produce.fetch_video(url,DEST/'episode01-part01-wan3-native-480p.mp4')
                (DEST/'completion.json').write_text(json.dumps({'run_id':state['run_id'],'status':result['status'],'credits':result.get('credits')},indent=2))
                produce.summary('## Wan 3.0 第一段测试完成\n\n480p，15秒，九张独立分镜参考。请下载 artifact；原生语音需要逐句检查，不代表已保证台词或口型正确。')
                return
            time.sleep(10)
        raise TimeoutError('The accepted trial is still processing; preserve its run ID instead of submitting a replacement')


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc).replace(os.environ.get('PROTOFACE_API_KEY') or '\x00','[REDACTED]'),flush=True)
        raise SystemExit(1)
