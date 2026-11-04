"""Render a labelled animatic, or assemble generated clips with the same edit."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import subprocess
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
WORK = OUT / "edit"


def run(args):
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr[-6000:])


def ass_time(seconds):
    cs = round(seconds * 100)
    return f"{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}"


def srt_time(seconds):
    ms = round(seconds * 1000)
    return f"{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}"


def safe_ass(text):
    return text.replace("\\", "\\\\").replace("{", "（").replace("}", "）").replace("\n", "\\N")


def write_captions(manifest, preview=True):
    intro = manifest["intro_seconds"]
    body_end = intro + manifest["body_seconds"]
    end = body_end + manifest["outro_seconds"]
    styles = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: CN,Noto Sans CJK SC,30,&H00F5F2EB,&H000000FF,&H0012161D,&HA0000000,0,0,0,0,100,100,0,0,1,1.4,0,2,40,40,49,1
Style: EN,DejaVu Sans,22,&H00E4E6E8,&H000000FF,&H0012161D,&HA0000000,0,0,0,0,100,100,0,0,1,1,0,2,36,36,17,1
Style: Left,Noto Sans CJK SC,23,&H00DBE2E8,&H000000FF,&H0012161D,&H00000000,0,0,0,0,100,100,1,0,1,0,0,7,28,28,10,1
Style: Center,Noto Sans CJK SC,23,&H00DBE2E8,&H000000FF,&H0012161D,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,25,25,10,1
Style: Right,Noto Sans CJK SC,22,&H00DBE2E8,&H000000FF,&H0012161D,&H00000000,0,0,0,0,100,100,0,0,1,0,0,9,28,28,10,1
Style: Label,Noto Sans CJK SC,16,&H0098A9B9,&H000000FF,&H0012161D,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,20,20,38,1
Style: Title,Noto Serif CJK SC,76,&H00E8E2D3,&H000000FF,&H0012161D,&H00000000,0,0,0,0,100,100,6,0,1,1,0,5,30,30,0,1
Style: Latin,DejaVu Sans,25,&H00BCA981,&H000000FF,&H0012161D,&H00000000,0,0,0,0,100,100,4,0,1,0,0,5,25,25,0,1
Style: Episode,Noto Sans CJK SC,32,&H00E8E2D3,&H000000FF,&H0012161D,&H00000000,0,0,0,0,100,100,2,0,1,0,0,5,25,25,0,1
Style: Credit,Noto Sans CJK SC,25,&H00C9CDD1,&H000000FF,&H0012161D,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,20,20,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    def event(start, stop, style, text, override="", layer=1):
        events.append(f"Dialogue: {layer},{ass_time(start)},{ass_time(stop)},{style},,0,0,0,,{override}{safe_ass(text)}")
    event(0, intro, "Title", "十三扇门", r"{\pos(640,245)\fad(280,250)}")
    event(0, intro, "Latin", "THIRTEEN DOORS", r"{\pos(640,312)\fad(280,250)}")
    event(0, intro, "Episode", "第4集 · 别数房间，数门", r"{\pos(640,395)\fad(300,250)}")
    event(0, intro, "Credit", "Episode 04 · Count Doors, Not Rooms", r"{\pos(640,445)\fad(300,250)}")
    event(0, intro, "Credit", "作者 林爱丽  /  Written by Lin Aili", r"{\pos(640,526)\fad(350,250)}")
    event(intro, body_end, "Left", "《十三扇门》")
    event(intro, body_end, "Center", "第4集《别数房间，数门》")
    event(intro, body_end, "Right", "作者 林爱丽")
    if preview:
        event(0, end, "Label", "动态分镜预览 · STORYBOARD ANIMATIC · 无配音 / NO DIALOGUE AUDIO")
    else:
        event(intro, body_end, "Label", "AI动画 · 中英字幕 · 配乐音效版（无配音）")
    srt = []
    for i, cue in enumerate(manifest["subtitles"], 1):
        start, stop = cue["start"] + intro, cue["end"] + intro
        event(start, stop, "CN", cue["zh"])
        event(start, stop, "EN", cue["en"])
        srt.append(f'{i}\n{srt_time(start)} --> {srt_time(stop)}\n{cue["zh"]}\n{cue["en"]}\n')
    event(body_end, end, "Episode", "未完待续", r"{\pos(640,290)\fad(220,350)}")
    event(body_end, end, "Latin", "TO BE CONTINUED", r"{\pos(640,350)\fad(220,350)}")
    event(body_end, end, "Credit", "《十三扇门》第4集 · 作者 林爱丽", r"{\pos(640,460)\fad(220,350)}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "episode04.ass").write_text(styles + "\n".join(events) + "\n")
    (OUT / "episode04.zh-en.srt").write_text("\n".join(srt))


def write_wav(path, data, rate=24000):
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(2)
        stream.setsampwidth(2)
        stream.setframerate(rate)
        stream.writeframes((np.clip(data, -0.95, 0.95) * 32767).astype("<i2").tobytes())


def soundtrack(manifest):
    """Original procedural suspense score and Foley; no copied music or speech."""
    rate = 24000
    duration = manifest["intro_seconds"] + manifest["body_seconds"] + manifest["outro_seconds"]
    t = np.arange(round(duration * rate)) / rate
    rng = np.random.default_rng(1304)
    swell = 0.55 + 0.20 * np.sin(2 * np.pi * 0.043 * t) + 0.1 * np.sin(2 * np.pi * 0.013 * t)
    drone = (0.075*np.sin(2*np.pi*55*t) + 0.028*np.sin(2*np.pi*82.4*t)
             + 0.018*np.sin(2*np.pi*110*t) + 0.012*np.sin(2*np.pi*113.7*t)) * swell
    pulse = 0.012 * np.sin(2*np.pi*41.2*t) * (0.5+0.5*np.sin(2*np.pi*0.84*t))**6
    upper = 0.006 * (np.sin(2*np.pi*329*t)+np.sin(2*np.pi*330.4*t)) * np.maximum(0,np.sin(2*np.pi*0.037*t))
    fade = np.minimum(t/2, 1) * np.minimum(np.maximum((duration-t)/2, 0), 1)
    # Pull the score down at the cliffhanger, leaving the last turn exposed.
    tension_drop = 1 - 0.88 * np.clip((t-61.0)/0.4, 0, 1)
    music = (drone + pulse + upper) * fade * tension_drop
    stereo_music = np.stack([music, np.roll(music, 89)*0.98], axis=1)
    write_wav(OUT / "original-suspense-bgm.wav", stereo_music)
    white = rng.normal(0, 1, len(t))
    rain = (white - np.roll(white, 1)) * 0.005 * fade
    radio = rng.normal(0, 1, len(t)) * 0.008
    mask = ((t >= 5) & (t < 16.8)) | ((t >= 47) & (t < 49.5))
    effects = rain + radio * mask
    def hit(at, length, level, kind):
        start = round(at*rate); n = min(round(length*rate), len(t)-start)
        u = np.arange(n)/rate
        if kind == "knock":
            sample = (np.sin(2*np.pi*135*u) + .4*np.sin(2*np.pi*287*u)) * np.exp(-u*25)
        elif kind == "metal":
            sample = (np.sin(2*np.pi*1850*u)+.6*np.sin(2*np.pi*2711*u)) * np.exp(-u*22)
        elif kind == "paper":
            sample = rng.normal(0, .45, n)*np.sin(np.pi*u/length)**2
        else:
            sample = rng.normal(0, .6, n)*np.exp(-u*16)
        effects[start:start+n] += level*sample
    for at in [25.6, 26.05, 27.3]: hit(at,.32,.11,"knock")
    hit(29.8,.30,.045,"metal")
    hit(32.8,.25,.07,"metal")
    hit(33.6,.42,.10,"crack")
    hit(37.8,.55,.035,"paper")
    hit(59.3,.50,.04,"paper")
    mix = stereo_music + np.stack([effects, np.roll(effects, 47)], axis=1)
    peak = np.max(np.abs(mix))
    if peak > .85: mix *= .85 / peak
    write_wav(OUT / "music-and-sfx.wav", mix)


def make_still_clip(shot, destination, seconds, dim=False):
    x,y,w,h = shot["crop"]
    frames = round(seconds*24)
    filters = [f"crop={w}:{h}:{x}:{y}",
               "scale=1280:600:force_original_aspect_ratio=decrease",
               "pad=1280:600:(ow-iw)/2:(oh-ih)/2:color=0x0b0e14", "setsar=1",
               f"zoompan=z='1+on*0.00045':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s=1280x600:fps=24",
               "pad=1280:720:0:48:color=0x0b0e14"]
    if dim: filters += ["drawbox=x=0:y=0:w=iw:h=ih:color=black@0.68:t=fill"]
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-filter_threads","1",
         "-i",str(ROOT/shot["image"]),"-vf",",".join(filters),"-frames:v",str(frames),
         "-an","-c:v","libx264","-preset","veryfast","-crf","20","-pix_fmt","yuv420p",
         "-threads","2",str(destination)])


def make_generated_clip(shot, source, destination):
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-filter_threads","1",
         "-i",str(source),"-vf",
         "fps=24,scale=1280:600:force_original_aspect_ratio=decrease,pad=1280:600:(ow-iw)/2:(oh-ih)/2:color=0x0b0e14,setsar=1,pad=1280:720:0:48:color=0x0b0e14",
         "-t",str(shot["duration"]),"-an","-c:v","libx264","-preset","veryfast","-crf","20",
         "-pix_fmt","yuv420p","-threads","2",str(destination)])


def render(generated=None):
    manifest = json.loads((ROOT/"production/episode04.json").read_text())
    WORK.mkdir(parents=True, exist_ok=True)
    write_captions(manifest, preview=generated is None)
    soundtrack(manifest)
    entries=[]
    intro=WORK/"00-intro.mp4"
    make_still_clip(manifest["shots"][0],intro,manifest["intro_seconds"],dim=True)
    entries.append(intro)
    def one(item):
        index,shot=item
        dest=WORK/f"{index+1:02}-{shot['id']}.mp4"
        if generated:
            source=Path(generated)/f"{shot['id']}.mp4"
            if not source.is_file(): raise RuntimeError(f"Missing generated clip: {source}")
            make_generated_clip(shot,source,dest)
        else:
            make_still_clip(shot,dest,shot["duration"])
        print(f"Prepared {shot['id']}",flush=True)
        return dest
    with ThreadPoolExecutor(max_workers=3) as pool:
        entries.extend(pool.map(one,enumerate(manifest["shots"])))
    outro=WORK/"31-outro.mp4"
    make_still_clip(manifest["shots"][-1],outro,manifest["outro_seconds"],dim=True)
    entries.append(outro)
    concat=WORK/"concat.txt"
    concat.write_text("\n".join(f"file '{path.name}'" for path in entries)+"\n")
    silent=WORK/"joined.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0",
         "-i",str(concat),"-c","copy",str(silent)])
    name="episode04-animated.mp4" if generated else "episode04-storyboard-preview.mp4"
    run(["ffmpeg","-hide_banner","-loglevel","error","-y","-filter_threads","1",
         "-i",str(silent),"-i",str(OUT/"music-and-sfx.wav"),"-vf",f"ass={OUT/'episode04.ass'}",
         "-map","0:v:0","-map","1:a:0","-c:v","libx264","-preset","veryfast","-crf","19",
         "-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-movflags","+faststart",
         "-threads","3","-shortest",str(OUT/name)])
    print(OUT/name,flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--generated-clips",help="Directory with all 30 generated ep04-NNN.mp4 files")
    args=parser.parse_args()
    render(args.generated_clips)
