"""Preflight three approved native-audio parts and assemble the accepted first part."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

import httpx
from jsonschema import Draft202012Validator

import produce_video as production

ROOT=Path(__file__).resolve().parent


def preflight():
    key=os.environ.get('PROTOFACE_API_KEY','').strip()
    if not key:
        raise RuntimeError('PROTOFACE_API_KEY repository secret is missing')
    with httpx.Client(base_url='https://api.protoface.com',
                      headers={'Authorization':'Bearer '+key},timeout=90,
                      follow_redirects=False) as client:
        model=production.api(client,'GET','/v1/models/'+production.MODEL)
        if not model.get('available'):
            raise RuntimeError('MiniMax H3 is unavailable; no generation submitted')
        estimate=production.price(model,include_audio=False)
        records=[]
        for n in (2,3,4):
            packet=production.read_packet(n,'packed-fresh')
            text=(ROOT/'prompts-fresh'/f'part-{n:02}.txt').read_text()
            if packet['prompt']!=text:
                raise ValueError('Prompt file differs from approved input packet')
            Draft202012Validator(model['request_schemas']['video.general']).validate(
                production.payload(packet,None))
            records.append({'part':n,'estimated_credits':estimate,
                            'image_sha256':packet['image']['sha256'],
                            'prompt_sha256':hashlib.sha256(text.encode()).hexdigest()})
        total=sum(x['estimated_credits'] for x in records)
        quota=production.api(client,'GET','/v1/billing/quota')
        if quota.get('balance_credits',0)<total:
            raise RuntimeError('Balance cannot cover all three parts; no generation submitted')
    production.save(ROOT/'fresh-preflight'/'preflight.json',{
        'model':production.MODEL,'parts':records,'estimated_total_credits':total,
        'requested_duration_seconds':45,'quality':'480p','audio_reference':False,
        'first_part_reused_from_run':41916935045,'paid_retries':False})
    print('Validated three fresh grids and exact dialogue lists; estimated total credits:',total)


def assemble(folder,output):
    output.mkdir(parents=True,exist_ok=True)
    paths=[folder/f'C01_EP01_part-{n:02}_USERPROMPT_480p.mp4' for n in (1,2,3,4)]
    media=[]
    for path in paths:
        info=production.inspect(path,15)
        if not any(s['codec_type']=='audio' for s in info['streams']):
            raise ValueError('A segment has no native audio track')
        media.append({'file':path.name,'info':info})
    concat=output/'native-concat.txt'
    concat.write_text(''.join("file '"+str(p.resolve())+"'\n" for p in paths))
    target=output/'C01_EP01_480p_60s_FRESH.mp4'
    production.run(['ffmpeg','-v','error','-y','-threads','2','-filter_threads','1',
        '-f','concat','-safe','0','-i',str(concat),'-map','0:v:0','-map','0:a:0','-sn','-dn',
        '-vf','fps=24,setsar=1,tpad=stop_mode=clone:stop_duration=0.3',
        '-t','60','-frames:v','1440','-c:v','libx264','-preset','veryfast','-crf','19',
        '-threads','2','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k',
        '-metadata','title=十三扇门 第1集 被抹除的地址，三声敲门',
        '-metadata','artist=林爱丽','-movflags','+faststart',str(target)])
    result=production.inspect(target,60)
    production.save(output/'render-info.json',{
        'first_part_reused_from_run':41916935045,'parts':media,'output':result,
        'native_audio_retained':True,'subtitle_overlay_added':False,
        'music_added_in_edit':False,'dialogue_expected':production.SCRIPT,
        'content_review':'Compare all generated shots and transcribe native speech before claiming fidelity.'})
    print('Assembled 60 seconds from the four native-audio clips:',target.name)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['preflight','assemble'])
    parser.add_argument('--folder',type=Path,default=ROOT/'native-collected')
    parser.add_argument('--output',type=Path,default=ROOT/'fresh-output')
    args=parser.parse_args()
    if args.mode=='preflight':preflight()
    else:assemble(args.folder,args.output)


if __name__=='__main__':
    try:main()
    except Exception as exc:
        print(str(exc).replace(os.environ.get('PROTOFACE_API_KEY') or '\x00','[REDACTED]'))
        raise SystemExit(1)
