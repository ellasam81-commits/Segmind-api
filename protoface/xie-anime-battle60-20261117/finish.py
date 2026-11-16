from pathlib import Path
import subprocess,json
P=Path(__file__).resolve().parent;O=P/'output';G=P/'generated';O.mkdir(exist_ok=True)
def run(cmd):
 r=subprocess.run(cmd,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-2000:])
files=[]
for i in range(1,7):
 src=G/f'scene-{i:02}.mp4';dst=O/f'clip-{i:02}.mp4'
 run(['ffmpeg','-v','error','-y','-i',str(src),'-vf','scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=1,trim=end_frame=300,setpts=N/(30*TB),format=yuv420p','-af','aresample=48000,apad,atrim=duration=10,afade=t=in:d=0.02,afade=t=out:st=9.97:d=0.03','-c:v','libx264','-threads','2','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-r','30','-video_track_timescale','30000','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t','10',str(dst)]);files.append(dst)
(O/'concat.txt').write_text(''.join("file '"+str(p)+"'\n" for p in files));run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(O/'concat.txt'),'-c','copy',str(O/'body.mp4')])
ass='''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,Noto Serif CJK SC,30,&H009FE4FF,&H000000FF,&H00251B10,&H80000000,-1,0,0,0,100,100,1,0,1,1.2,0,7,26,26,32,1
Style: Note,Noto Sans CJK SC,17,&H00E5E5E5,&H000000FF,&H00251B10,&H80000000,0,0,0,0,100,100,0,0,1,1,0,9,26,26,36,1
Style: End,Noto Serif CJK SC,70,&H009FE4FF,&H000000FF,&H00251B10,&H80000000,-1,0,0,0,100,100,5,0,1,1.5,0,2,30,30,115,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:57.00,Title,,0,0,0,,谢却山 · 破阵
Dialogue: 0,0:00:00.00,0:01:00.00,Note,,0,0,0,,AI动漫二创 · 非官方剧情
Dialogue: 1,0:00:57.00,0:01:00.00,End,,0,0,0,,{\\fad(250,350)}何不同舟渡\\N{\\fs30\\fsp2}谢却山 · 破阵
''';(O/'film.ass').write_text(ass)
dst=O/'XieQueshan_2D_Anime_Battle_60s.mp4';bgm=P.parent/'episode05/assets/幻火.mp3'
filters=f"[0:v]ass=filename='{O/'film.ass'}',fade=t=out:st=59.65:d=0.35,format=yuv420p[v];[0:a]volume=1.0[a];[1:a]atrim=duration=60,asetpts=PTS-STARTPTS,volume=0.16,afade=t=in:d=0.4,afade=t=out:st=58:d=2[m];[a][m]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=10[au]"
run(['ffmpeg','-v','error','-y','-i',str(O/'body.mp4'),'-i',str(bgm),'-filter_complex',filters,'-map','[v]','-map','[au]','-c:v','libx264','-threads','3','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-tag:v','avc1','-r','30','-video_track_timescale','30000','-c:a','aac','-b:a','192k','-ar','48000','-ac','2','-t','60','-movflags','+faststart',str(dst)])
run(['ffmpeg','-v','error','-i',str(dst),'-f','null','-']);r=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(dst)]));(O/'qa.json').write_text(json.dumps(r,indent=2));assert r['streams'][0]['nb_frames']=='1800';print(dst,flush=True)
