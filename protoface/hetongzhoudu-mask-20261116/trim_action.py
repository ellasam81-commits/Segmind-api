"""Apply both requested action trims to the photo master in one encode."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output'
SOURCE=OUT/'何不同舟渡_面具之下_真人剧照片尾版.mp4'
DEST=OUT/'何不同舟渡_面具之下_动作精剪版.mp4'
CUTS=[(552,581),(847,885)];RATE=30;HALF=.04
frames=1350-sum(b-a for a,b in CUTS);duration=frames/RATE
ranges=[(0,552),(581,847),(885,1350)]
f=['[0:v]split=3[v0][v1][v2]','[0:a]asplit=3[a0][a1][a2]']
for i,(start,end) in enumerate(ranges):
    f.append(f'[v{i}]trim=start_frame={start}:end_frame={end},setpts=PTS-STARTPTS[p{i}]')
    aa=start/RATE-(HALF if i else 0);bb=end/RATE+(HALF if i<2 else 0)
    f.append(f'[a{i}]atrim=start={aa}:end={bb},asetpts=PTS-STARTPTS[b{i}]')
f+=['[p0][p1][p2]concat=n=3:v=1:a=0,setsar=1[v]','[b0][b1]acrossfade=d=0.08:c1=qsin:c2=qsin[ab]','[ab][b2]acrossfade=d=0.08:c1=qsin:c2=qsin,aresample=48000[a]']
subprocess.run(['ffmpeg','-y','-v','error','-i',str(SOURCE),'-filter_complex',';'.join(f),'-map','[v]','-map','[a]','-t',str(duration),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-movflags','+faststart',str(DEST)],check=True)
report={'source':SOURCE.name,'output':DEST.name,'cuts_source_frames':CUTS,'cuts_source_seconds':[[a/RATE,b/RATE] for a,b in CUTS],'new_arrow_cut_in_previous_version_seconds':[818/30,856/30],'newly_removed_seconds':38/30,'duration_seconds':duration,'audio_crossfade_seconds':.08,'reason':'Retain previous first-sword correction and shorten floating arrow entrance, cutting to the parry. Render both from photo master to avoid another generational encode.'}
(ROOT/'action-trim.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
