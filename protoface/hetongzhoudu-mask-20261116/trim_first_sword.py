"""Remove the user-flagged first sword artifact while preserving dialogue sync."""
from pathlib import Path
import argparse,json,subprocess
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output'
p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,default=OUT/'何不同舟渡_面具之下_真人剧照片尾版.mp4')
p.add_argument('--output',type=Path,default=OUT/'何不同舟渡_面具之下_拿剑修剪版.mp4')
a=p.parse_args()
START=552/30;END=581/30;REMOVED=END-START;DURATION=45-REMOVED
# Hard picture cut to the existing mask close-up. Audio overlaps by 80 ms
# centered on the cut, preserving the exact subsequent audio/video offset.
f=f'''[0:v]split=2[v0][v1];
[v0]trim=end_frame=552,setpts=PTS-STARTPTS[p0];
[v1]trim=start_frame=581,setpts=PTS-STARTPTS[p1];
[p0][p1]concat=n=2:v=1:a=0,setsar=1[v];
[0:a]asplit=2[a0][a1];
[a0]atrim=end={START+.04},asetpts=PTS-STARTPTS[b0];
[a1]atrim=start={END-.04},asetpts=PTS-STARTPTS[b1];
[b0][b1]acrossfade=d=0.08:c1=qsin:c2=qsin,aresample=48000[a]'''.replace('\n','')
subprocess.run(['ffmpeg','-y','-v','error','-i',str(a.source),'-filter_complex',f,'-map','[v]','-map','[a]','-t',str(DURATION),'-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-movflags','+faststart',str(a.output)],check=True)
report={'source':a.source.name,'output':a.output.name,'removed_source_interval_seconds':[START,END],'removed_frames':29,'duration_seconds':DURATION,'audio_crossfade_seconds':.08,'reason':'Remove unnatural first sword handling and cut directly to masked close-up; preserve actual-photo end card and all dialogue.'}
(ROOT/'sword-trim.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
