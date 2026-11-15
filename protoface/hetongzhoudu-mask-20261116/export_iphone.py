"""Create a standards-constrained iPhone-compatible MP4 from the final cut."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output'
p=argparse.ArgumentParser()
p.add_argument('--source',type=Path,default=OUT/'何不同舟渡_面具之下_动作精剪版.mp4')
p.add_argument('--output',type=Path,default=OUT/'XieQueshan_iPhone.mp4')
a=p.parse_args()
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(a.source)]))
v=next(s for s in probe['streams'] if s['codec_type']=='video');frames=int(v['nb_frames']);duration=frames/30
source_range='pc' if v.get('color_range')=='pc' else 'tv'
# Explicit CFR, encoder time base and codec level avoid concat inheriting a
# microsecond time base and auto-signalling an unnecessarily high H.264 level.
vf=f'scale=in_range={source_range}:out_range=tv,format=yuv420p,fps=30,tpad=stop_mode=clone:stop_duration=0.04,trim=end_frame={frames},settb=1/30,setpts=N/(30*TB)'
cmd=['ffmpeg','-y','-v','warning','-i',str(a.source),'-map','0:v:0','-map','0:a:0','-map_metadata','-1','-map_chapters','-1','-vf',vf,'-c:v','libx264','-profile:v','main','-level:v','4.0','-preset','fast','-crf','18','-maxrate','8000k','-bufsize','16000k','-pix_fmt','yuv420p','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-r','30','-fps_mode','cfr','-enc_time_base:v','1:30','-video_track_timescale','30000','-tag:v','avc1','-c:a','aac','-profile:a','aac_low','-ar','48000','-ac','2','-b:a','192k','-af','aresample=async=1:first_pts=0','-t',str(duration),'-movflags','+faststart','-brand','mp42',str(a.output)]
r=subprocess.run(cmd,capture_output=True,text=True)
if r.returncode:raise RuntimeError(r.stderr[-4000:])
q=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(a.output)]))
v2=next(s for s in q['streams'] if s['codec_type']=='video');a2=next(s for s in q['streams'] if s['codec_type']=='audio')
assert v2['codec_name']=='h264' and v2['profile']=='Main' and v2['level']==40
assert v2['pix_fmt']=='yuv420p' and v2['color_range']=='tv'
assert v2['avg_frame_rate']=='30/1' and v2['r_frame_rate']=='30/1' and v2['time_base']=='1/30000'
assert int(v2['nb_frames'])==frames and a2['codec_name']=='aac' and a2['profile']=='LC'
subprocess.run(['ffmpeg','-v','error','-i',str(a.output),'-f','null','-'],check=True)
report={'source':a.source.name,'output':a.output.name,'source_video':{k:v.get(k) for k in ['profile','level','pix_fmt','color_range','time_base','avg_frame_rate']},'output_video':{k:v2.get(k) for k in ['profile','level','pix_fmt','color_range','time_base','avg_frame_rate','nb_frames','duration']},'output_audio':{k:a2.get(k) for k in ['codec_name','profile','sample_rate','channels','duration']},'duration':q['format']['duration'],'bytes':q['format']['size'],'full_decode':'passed','device_save_test':'Not possible on the user iPhone from this environment'}
(ROOT/'iphone-export-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False))
