"""Rebuild the already approved picture edit, without burned-in captions."""
import json,subprocess
from pathlib import Path

def build(project,root,out,original):
 p=json.loads((root/'clean-plan.json').read_text())[project];clips=[]
 for n in range(1,5):
  src=original(project,f'scene-{n:02}');ranges=p['ranges'][str(n)];f=[]
  for k,(a,b) in enumerate(ranges):
   crop=p['crops'].get(str(n),{}).get(str(k));cf='crop='+':'.join(map(str,crop))+',' if crop else ''
   f.append(f'[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS,{cf}scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1[v{k}]')
  f.append(''.join(f'[v{k}]' for k in range(len(ranges)))+f'concat=n={len(ranges)}:v=1:a=0,fps=30,tpad=stop_mode=clone:stop_duration=0.1,trim=end_frame={p["frames"][n-1]},settb=1/30,setpts=N/(30*TB),fps=30,format=yuv420p[v]')
  dst=out/f'{project}-normalized-{n:02}.mp4'
  subprocess.run(['ffmpeg','-v','error','-y','-i',str(src),'-filter_complex',';'.join(f),'-map','[v]','-an','-c:v','libx264','-preset','fast','-crf','18','-r','30','-fps_mode','cfr','-enc_time_base:v','1:30','-video_track_timescale','30000',str(dst)],check=True);clips.append(dst)
 inputs=[];f=[]
 for n,src in enumerate(clips):
  inputs+=['-i',str(src)];f.append(f'[{n}:v]settb=1/30,setpts=PTS-STARTPTS,fps=30,format=yuv420p[v{n}]')
 current='v0';cross=p['cross_frames']/30
 for n in range(1,4):
  offset=sum(p['frames'][:n])/30-cross*n;f.append(f'[{current}][v{n}]xfade=transition=fade:duration={cross}:offset={offset}[x{n}]');current=f'x{n}'
 frames=sum(p['frames'])-3*p['cross_frames'];f.append(f'[{current}]fps=30,tpad=stop_mode=clone:stop_duration=0.1,trim=end_frame={frames},settb=1/30,setpts=N/(30*TB),fps=30,format=yuv420p[v]')
 dst=out/(project+'-clean-body.mp4')
 subprocess.run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex_threads','1','-filter_complex',';'.join(f),'-map','[v]','-an','-c:v','libx264','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-r','30','-fps_mode','cfr','-enc_time_base:v','1:30','-video_track_timescale','30000',str(dst)],check=True)
 return dst,frames/30
