from pathlib import Path
import subprocess,json,hashlib
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parent;O=P/'output';O.mkdir(exist_ok=True)
def run(c):subprocess.run(c,check=True,capture_output=True)
for slug,label,name in [('ltx','LTX 2.5 Fast','XieQueshan_War_Anime_LTX25.mp4'),('h3','MiniMax H3','XieQueshan_War_Anime_H3.mp4')]:
 src=P/(slug+'.mp4');dst=O/name
 ass='''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Label,Noto Sans CJK SC,26,&H00C7E9FF,&H000000FF,&H00302010,&H80000000,0,0,0,0,100,100,0,0,1,1,0,7,24,24,28,1
Style: Note,Noto Sans CJK SC,18,&H00EEEEEE,&H000000FF,&H00302010,&H80000000,0,0,0,0,100,100,0,0,1,0.7,0,2,20,20,24,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''+f'Dialogue: 0,0:00:00.00,0:00:10.00,Label,,0,0,0,,{label}\nDialogue: 0,0:00:00.00,0:00:10.00,Note,,0,0,0,,谢却山 · AI动漫二创 · 非官方剧情\n'
 a=P/(slug+'.ass');a.write_text(ass)
 run(['ffmpeg','-v','error','-y','-i',str(src),'-vf',f"scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30,ass=filename='{a}',format=yuv420p",'-c:v','libx264','-threads','3','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-tag:v','avc1','-video_track_timescale','30000','-af','loudnorm=I=-16:TP=-1.5:LRA=9','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t','10','-movflags','+faststart',str(dst)])
 r=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(dst)]));(O/(slug+'-qa.json')).write_text(json.dumps(r,indent=2));run(['ffmpeg','-v','error','-i',str(dst),'-f','null','-'])
 print(dst.name,r['format']['duration'],flush=True)
