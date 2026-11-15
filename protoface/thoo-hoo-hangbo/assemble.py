"""Render all six approved Protoface clips into a single credited 42-second MP4.

No API requests and no charge: only ffmpeg on existing local MP4s.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("protoface/thoo-hoo-hangbo")
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("thoo-hoo-hangbo-output")
SCENES = json.loads((ROOT / "scenes.json").read_text(encoding="utf-8"))["scenes"]
NAME = "挂播_挂在哪儿_制作林爱丽_42秒.mp4"
FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc",
)
def call(args):
    print("ffmpeg operation:", args[0], args[-1], flush=True)
    subprocess.run(args, check=True)

def video_audio(src):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1", str(src)],
        capture_output=True, text=True, check=True,
    )
    return bool(result.stdout.strip())

def normalize(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    has_audio = video_audio(src)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src)]
    if not has_audio:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])
    cmd.extend([
        "-map", "0:v:0", "-map", "0:a:0" if has_audio else "1:a:0",
        "-vf", "fps=24,scale=1280:720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1,"
               "tpad=stop_mode=clone:stop_duration=7,format=yuv420p",
        "-af", "aresample=async=1:first_pts=0,apad",
        "-t", "7", "-r", "24",
        "-c:v", "libx264", "-crf", "21", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-ac", "2",
        "-b:a", "160k", "-movflags", "+faststart", str(dst)
    ])
    call(cmd)

def make_srt():
    entries = []
    for i, shot in enumerate(SCENES):
        start = i * 7
        # Exact SRT frame range sits within one 7-second clip.
        entries.append(
            f"{i+1}\n00:00:{start:02d},350 --> 00:00:{start+6:02d},650\n"
            f"{shot['sub']}\n"
        )
    srt = OUT / "subtitles.srt"
    srt.write_text("\n".join(entries), encoding="utf-8")
    return srt

def main():
    if len(SCENES) != 6:
        raise ValueError("Expected exactly six scenes.")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe must be installed.")
    font = next((Path(f) for f in FONT_CANDIDATES if Path(f).is_file()), None)
    if not font:
        raise RuntimeError("Chinese font Noto CJK is missing. Install fonts-noto-cjk.")
    paths = [OUT / f"scene-{i:02d}.mp4" for i in range(1, 7)]
    missing = [str(p) for p in paths if not p.is_file()]
    if missing:
        raise RuntimeError("Cannot assemble yet. Missing video clips: " + ", ".join(missing))
    srt = make_srt()
    normalized_dir = OUT / "normalized"
    for i, source in enumerate(paths, start=1):
        normalize(source, normalized_dir / f"scene-{i:02d}.mp4")
    concat_list = OUT / "clips.txt"
    concat_list.write_text(
        "".join(f"file 'normalized/scene-{i:02d}.mp4'\n" for i in range(1, 7)),
        encoding="utf-8",
    )
    clean = OUT / "master_uncredited.mp4"
    call([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", "-movflags", "+faststart", str(clean),
    ])
    # Permanent upper-right maker credit, editable SRT also exported.
    credit = (
        f"drawtext=fontfile={font.as_posix()}:"
        "text='制作 林爱丽':fontcolor=white:fontsize=30:"
        "x=w-text_w-35:y=28:borderw=3:bordercolor=black@0.75:"
        "shadowx=1:shadowy=1:shadowcolor=black@0.5"
    )
    subtitles = (
        f"subtitles={srt.as_posix()}:"
        "force_style='FontName=Noto Sans CJK SC,FontSize=20,Alignment=2,"
        "MarginV=30,Outline=2,Shadow=1'"
    )
    final = OUT / NAME
    call([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(clean), "-vf", credit + "," + subtitles,
        "-c:v", "libx264", "-crf", "20", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-c:a", "copy",
        "-movflags", "+faststart", str(final),
    ])
    print("ASSEMBLY SUCCESS:", final, "size", final.stat().st_size, flush=True)
    print("CREDIT: 制作 林爱丽 (permanent top right) | SUBTITLES: Chinese burned in & SRT included")

if __name__ == "__main__":
    main()
