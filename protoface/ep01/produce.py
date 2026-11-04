"""Four nine-reference clips with native dialogue, then a one-minute edit."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import time
import wave

import httpx
from jsonschema import Draft202012Validator
import numpy as np

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"output"
STATE=ROOT/"checkpoint"
MODEL="minimax/minimax-h3"


def cmd(args):
    p=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode: raise RuntimeError(p.stderr[-4000:])


def summary(text):
    path=os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path,"a",encoding="utf-8") as out: out.write(text+"\n\n")


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(".tmp");temp.write_text(json.dumps(value,ensure_ascii=False,indent=2));temp.replace(path)


def api(client,method,path,**kwargs):
    # A create is attempted once; the same workflow run reuses its key on rerun.
    r=client.request(method,path,**kwargs)
    if not r.is_success:
        try:
            detail=r.json().get("error",{})
            error=detail.get("code","request_failed")+": "+str(detail.get("message",""))
        except (ValueError,AttributeError): error="request_failed"
        raise RuntimeError(f"Protoface HTTP {r.status_code}: {error}")
    return r.json()


def unpack():
    for page in sorted((ROOT/"packed").glob("board-*.json")):
        entries=json.loads(page.read_text())
        if len(entries)!=9: raise ValueError("Every board must contain exactly nine references")
        for name,item in entries.items():
            if not re.fullmatch(r"refs/board-0[1-4]/0[1-9]\.jpg",name): raise ValueError("Invalid reference path")
            data=base64.b64decode(item["data"],validate=True)
            if hashlib.sha256(data).hexdigest()!=item["sha256"]: raise ValueError("Reference checksum failed")
            path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)


def data_uri(path,kind="image/jpeg"):
    return "data:"+kind+";base64,"+base64.b64encode(path.read_bytes()).decode()


def prompt_for(manifest,part):
    offset=(part["number"]-1)*15
    lines=[
      "严格按按顺序输入的9张独立剧情参考图制作15秒、16:9横版二维动漫恐怖悬疑短片。",
      "参考图1至9的顺序即播放顺序，等价于九宫格上排左中右、中排左中右、下排左中右。",
      "每个画面单独铺满屏幕，以硬切连接，绝不出现拼贴、九宫格、边框、编号、标题、说明文字或底部参考表。",
      "保留每张参考的人脸、黑色长风衣、高领毛衣、发型、棕色斜挎包、人物位置、左右手、道具数量、场景和构图。",
      "只能轻微运镜、自然动作和克制表情，不擅自换角度、不增加人物或剧情。只有成年男主沈照夜，无安宁、无女声、无鬼影。",
      "本集只用一把无数字普通铜钥匙，不能出现13刻字。无BGM、无歌曲、无旁白、无字幕。",
      "必须生成音频，严格逐字使用下面的原台词，其他时间不说话；同一低沉克制冷静的成年男声，普通话。",
      "画面看得到男主嘴部时口型同步；道具特写或空镜时是他的画外对白，不能把嘴画到道具上，不能另造说话的人。",
      "只保留规定对白、轻呼吸、脚步、门轴、纸张、键盘及环境音。敲门音由后期精确添加，本次不要自行生成敲门或冲击音，以免声数重复。",
      "纸面地址和电脑界面的文字是场景道具内容，保留参考原字，不生成额外文字。",
    ]
    if (STATE/"male-voice-reference.mp3").is_file() and part["number"]>1:
        lines.append("音频参考1是前一片段已确定的沈照夜声音；只匹配其音色，不重复参考里的内容。")
    lines.append("九个镜头的精确时段和动作：")
    for p in part["panels"]:
        lines.append(f"图{p['number']}，{p['start']:.1f}–{p['end']:.1f}秒：{p['action']}")
    lines.append("严格原台词与片段内时段（不朗读角色名或时码）：")
    for cue in manifest["dialogue"]:
        if offset<=cue["start"]<offset+15:
            tag="画外对白" if cue["offscreen"] else "对白"
            lines.append(f"{cue['start']-offset:.1f}–{cue['end']-offset:.1f}秒，沈照夜（男，{tag}）：{cue['zh']}")
    lines.append("第4段结尾只看见空楼梯间，停在‘头顶？’的悬念，不展示敲门者。" if part["number"]==4 else "结尾保持与下一段自然衔接，不加片尾、黑场或字幕。")
    return "\n".join(lines)


def payload_for(manifest,part,schema,quality):
    if len(part["panels"])!=9: raise ValueError("A part must have nine panels")
    payload={"prompt":prompt_for(manifest,part),"reference":[data_uri(ROOT/p["image"]) for p in part["panels"]],
             "duration_seconds":15,"aspect_ratio":"16:9","quality":quality,
             "generate_audio":True,"enhance_prompt":False}
    voice=STATE/"male-voice-reference.mp3"
    if part["number"]>1 and voice.is_file(): payload["audio"]=[data_uri(voice,"audio/mpeg")]
    Draft202012Validator(schema).validate(payload)
    return payload


def identifier(workflow,part,payload):
    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()[:20]
    return f"ep01-nine-{workflow}-{part}-{digest}"


def inspect_clip(path):
    p=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries",
          "format=duration:stream=codec_type,width,height","-of","json",str(path)]))
    streams=p.get("streams",[])
    if not any(s.get("codec_type")=="audio" for s in streams): raise ValueError("Generated clip has no dialogue/audio track")
    video=next((s for s in streams if s.get("codec_type")=="video"),None)
    # Providers align the requested widescreen canvas to codec blocks (e.g.1344x768).
    # Accept that small difference, then pad to exact16:9 without cutting the image.
    if not video or abs(video["width"]-video["height"]*16/9)>64: raise ValueError("Generated clip must have a widescreen video stream")
    if abs(float(p.get("format",{}).get("duration",0))-15)>.3: raise ValueError("Provider output is not a fifteen-second clip")


def fetch_video(url,target):
    p=httpx.URL(url)
    if p.scheme!="https" or not p.host or p.userinfo: raise ValueError("Invalid video output URL")
    temp=target.with_suffix(".part")
    # Provider credentials are never forwarded to the media download host.
    with httpx.Client(timeout=120,follow_redirects=True) as downloader:
        with downloader.stream("GET",url) as r:
            r.raise_for_status()
            with temp.open("wb") as out:
                for chunk in r.iter_bytes(): out.write(chunk)
    inspect_clip(temp);temp.replace(target)


def generate_part(client,manifest,part,schema,quality,workflow):
    native=STATE/f"native-{part['number']:02}.mp4"
    record=STATE/f"part-{part['number']:02}.json"
    payload=payload_for(manifest,part,schema,quality)
    key=identifier(workflow,part["number"],payload)
    state=json.loads(record.read_text()) if record.exists() else {"idempotency_key":key}
    if state.get("idempotency_key")!=key: raise ValueError("Checkpoint inputs differ; use the original workflow revision when resuming")
    if native.is_file() and state.get("status")=="completed": inspect_clip(native);return native
    if not state.get("run_id"):
        save(record,state)
        created=api(client,"POST",f"/v1/run/{MODEL}",headers={"Idempotency-Key":key},json=payload)
        run_id=created.get("id","")
        if not re.fullmatch(r"run_[A-Za-z0-9_-]+",run_id): raise ValueError("Invalid provider run ID")
        state.update(run_id=run_id,status=created.get("status","queued"),credit_estimate=created.get("credit_estimate"));save(record,state)
        summary(f"第{part['number']}段：`{run_id}`，接受后返回的费用估算：`{json.dumps(state['credit_estimate'])}`")
    run_id=state["run_id"];print(f"Part {part['number']}: {run_id}",flush=True)
    end=time.monotonic()+1500
    while time.monotonic()<end:
        status=api(client,"GET",f"/v1/runs/{run_id}/status").get("status")
        state["status"]=status;save(record,state)
        print(f"Part {part['number']}: {status}",flush=True)
        if status in {"failed","canceled"}: raise RuntimeError(f"Part {part['number']} {status}; no automatic replacement submitted")
        if status=="completed":
            body=api(client,"GET",f"/v1/runs/{run_id}")
            if body.get("status")!="completed": raise ValueError("Run/status responses disagree")
            url=(body.get("video") or {}).get("url")
            if not url:
                url=next(((x.get("file") or {}).get("url") for x in body.get("outputs",[]) if x.get("modality")=="video"),None)
            if not url: raise ValueError("Completed run has no video output")
            fetch_video(url,native);save(record,state)
            return native
        if status not in {"queued","running"}: raise RuntimeError("Unexpected provider status")
        time.sleep(5)
    raise TimeoutError(f"{run_id} is still processing. Re-run the same GitHub run to resume; no cancellation was sent.")


def wav(path,mono,rate=24000):
    stereo=np.stack([mono,np.roll(mono,31)],axis=1)
    with wave.open(str(path),"wb") as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(rate)
        w.writeframes((np.clip(stereo,-.9,.9)*32767).astype("<i2").tobytes())


def sound_tracks(manifest):
    rate=24000;t=np.arange(60*rate)/rate
    score=(.048*np.sin(2*np.pi*55*t)+.018*np.sin(2*np.pi*82.4*t)+.008*np.sin(2*np.pi*113.7*t))
    score*=.6+.25*np.sin(2*np.pi*.043*t)
    score*=np.minimum(t/2,1)*np.clip((58.5-t)/4,0,1)
    # Leave the final knock sequence and last line exposed.
    wav(OUT/"original-suspense-bgm.wav",score)
    foley=np.zeros(15*rate)
    for global_time in manifest["knocks"]:
        at=global_time-45;u=np.arange(int(.65*rate))/rate
        hit=.23*(np.sin(2*np.pi*95*u)+.34*np.sin(2*np.pi*187*u))*np.exp(-u*11)
        start=round(at*rate);foley[start:start+len(hit)]+=hit
    wav(OUT/"six-scripted-knocks.wav",foley)


def ass_time(t):
    c=round(t*100);return f"{c//360000}:{c//6000%60:02}:{c//100%60:02}.{c%100:02}"


def srt_time(t):
    ms=round(t*1000);return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def captions(manifest):
    text="""[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CN,Noto Sans CJK SC,32,&H00F8F5EE,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,30,30,55,1
Style: EN,DejaVu Sans,22,&H00F0F0F0,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,1.7,1,2,30,30,24,1
Style: Head,Noto Sans CJK SC,21,&H00E4E7E8,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,1.5,0,7,25,25,16,1
Style: Author,Noto Sans CJK SC,22,&H00E4E7E8,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,1.5,0,9,25,25,16,1
Style: Title,Noto Serif CJK SC,58,&H00E3DCCB,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,4,0,1,2,0,5,30,30,0,1
Style: Small,Noto Sans CJK SC,25,&H00E4E7E8,&H000000FF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,1.5,0,5,25,25,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events=[];srt=[]
    def event(a,b,style,line,override=""):
        line=line.replace("{","（").replace("}","）")
        events.append(f"Dialogue: 1,{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{override}{line}")
    event(0,60,"Head","《十三扇门》第1集 · 被抹除的地址，三声敲门")
    event(0,60,"Author","作者 林爱丽")
    event(.15,2.5,"Title","十三扇门",r"{\pos(640,265)\fad(200,400)}")
    event(.15,2.5,"Small","THIRTEEN DOORS · EPISODE 01",r"{\pos(640,330)\fad(200,400)}")
    event(2.5,4.35,"Small","沈照夜 · 神秘调查员 / Shen Zhaoye · Investigator",r"{\pos(640,600)\fad(100,150)}")
    for i,c in enumerate(manifest["dialogue"],1):
        event(c["start"],c["end"],"CN",c["zh"]);event(c["start"],c["end"],"EN",c["en"])
        srt.append(f'{i}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["zh"]}\n{c["en"]}\n')
    (OUT/"episode01.ass").write_text(text+"\n".join(events)+"\n")
    (OUT/"episode01.zh-en.srt").write_text("\n".join(srt))


def assemble(manifest):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/"raw").mkdir(exist_ok=True)
    sound_tracks(manifest);captions(manifest)
    for n in range(1,5):
        src=STATE/f"native-{n:02}.mp4";inspect_clip(src)
        args=["ffmpeg","-hide_banner","-loglevel","error","-y","-filter_threads","1","-i",str(src)]
        if n==4:
            args += ["-i",str(OUT/"six-scripted-knocks.wav"),"-filter_complex",
                     "[0:a]apad=whole_dur=15[a];[a][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=false[m]",
                     "-map","0:v:0","-map","[m]"]
        else: args += ["-map","0:v:0","-map","0:a:0","-af","apad=whole_dur=15"]
        canvas="854:480" if os.environ.get("EPISODE_EXPORT_480P")=="true" else "1280:720"
        args += ["-vf",f"fps=24,scale={canvas}:force_original_aspect_ratio=decrease,pad={canvas}:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=0.3",
                 "-t","15","-c:v","libx264","-preset","veryfast","-crf","19","-pix_fmt","yuv420p",
                 "-c:a","aac","-ar","48000","-b:a","192k","-threads","2","-movflags","+faststart",str(OUT/f"raw/segment-{n:02}.mp4")]
        cmd(args)
    concat=OUT/"raw/concat.txt";concat.write_text("\n".join(f"file 'segment-{n:02}.mp4'" for n in range(1,5))+"\n")
    clean=OUT/"episode01-clean-dialogue.mp4"
    cmd(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",str(concat),
         "-t","60","-c","copy","-movflags","+faststart",str(clean)])
    final=OUT/"episode01-bilingual-bgm.mp4"
    cmd(["ffmpeg","-hide_banner","-loglevel","error","-y","-filter_threads","1",
         "-i",str(clean),"-i",str(OUT/"original-suspense-bgm.wav"),"-filter_complex",
         "[0:a]asplit=2[voice][side];[1:a][side]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=300[duck];[voice][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=false[m]",
         "-vf",f"ass={OUT/'episode01.ass'}","-map","0:v:0","-map","[m]","-t","60",
         "-c:v","libx264","-preset","veryfast","-crf","19","-pix_fmt","yuv420p","-threads","3",
         "-c:a","aac","-b:a","192k","-movflags","+faststart",str(final)])
    probe=json.loads(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","json",str(final)]))
    if abs(float(probe["format"]["duration"])-60)>.1: raise ValueError("Final edit is not exactly one minute")
    summary("## 第1集已合成\n\n作者 林爱丽。下载成片 artifact：4个15秒对白音效原片、60秒无字幕无配乐合并版，以及60秒中英字幕+BGM版。")


def generate(mode):
    if os.environ.get("ALLOW_PAID_GENERATION")!="true": raise RuntimeError("Paid generation is not enabled for this request")
    key=os.environ.get("PROTOFACE_API_KEY","").strip()
    if not key: raise RuntimeError("Missing repository secret PROTOFACE_API_KEY")
    workflow=os.environ.get("EPISODE_RESUME_RUN_ID") or os.environ.get("GITHUB_RUN_ID")
    if not workflow: raise RuntimeError("Missing workflow identity for duplicate prevention")
    unpack();STATE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/"episode.json").read_text())
    parts=manifest["parts"][:1] if mode=="generate_first_clip" else manifest["parts"]
    quality=os.environ.get("PROTOFACE_QUALITY","768p")
    with httpx.Client(base_url="https://api.protoface.com",headers={"Authorization":f"Bearer {key}"},timeout=90,follow_redirects=False) as client:
        model=api(client,"GET",f"/v1/models/{MODEL}")
        if model.get("available") is False: raise RuntimeError("MiniMax H3 is unavailable")
        schema=model.get("request_schemas",{}).get("video.general")
        if not isinstance(schema,dict): raise RuntimeError("Missing live model schema")
        # Validate every board before any paid create, including 9 references and native audio.
        for part in parts: payload_for(manifest,part,schema,quality)
        quota=api(client,"GET","/v1/billing/quota")
        if quota.get("balance_credits",0)<=0: raise RuntimeError("Empty Protoface credit balance")
        summary(f"## 《十三扇门》第1集\n\n本次生成{len(parts)}段，每段15秒；每段9张独立画面参考。原生男声对白，不生成BGM或外置字幕。")
        for part in parts:
            native=generate_part(client,manifest,part,schema,quality,workflow)
            if part["number"]==1 and not (STATE/"male-voice-reference.mp3").exists():
                cmd(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(native),"-vn","-ac","1","-ar","24000","-c:a","libmp3lame","-b:a","96k",str(STATE/"male-voice-reference.mp3")])
    if len(parts)==4: assemble(manifest)
    else: summary("第一段已生成，见 checkpoint artifact。新的完整生成属于新的请求，可能再次收费。")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--mode",choices=["generate_first_clip","generate_episode","assemble"],default="generate_episode")
    args=p.parse_args()
    try:
        if args.mode=="assemble": assemble(json.loads((ROOT/"episode.json").read_text()))
        else: generate(args.mode)
    except Exception as exc:
        message=str(exc).replace(os.environ.get("PROTOFACE_API_KEY") or "\x00","[REDACTED]")
        print(message,flush=True);summary("## 制作停止\n\n"+html.escape(message));raise SystemExit(1)
