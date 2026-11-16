"""Restore original narrative inserts lost by the provider's motion-transfer edit."""
from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'restored';OUT.mkdir(exist_ok=True)
# [start,end,crop(w,h,x,y)] on original approved clean timeline.
INSERTS={
'hetongzhoudu':[(14.9666667,18.4666667,None),(18.4666667,20.4333333,[562,1000,80,0])],
'hetongzhoudu-bottle':[(3.1,5.9333333,[300,534,100,20]),(5.9333333,8.8,[390,694,330,0]),(14.4,15.4333333,None),(17.6,19.3,[562,1000,80,0]),(19.3,21.2333333,[440,782,180,300]),(21.2333333,22.3,None),(22.3,25.1,[506,900,170,320])],
'hetongzhoudu-guard':[(3.5333333,5.8,[500,888,100,0]),(5.8,7.4333333,None),(7.4333333,9.5666667,[420,746,0,90]),(13.8,14.7,None),(17.8333333,19.1666667,None),(19.1666667,20.9,[380,676,0,180]),(27.9666667,29.2333333,None),(29.2333333,30.9666667,[450,800,140,0])]
}
FRAMES={'hetongzhoudu':1212,'hetongzhoudu-bottle':894,'hetongzhoudu-guard':929}
def sh(cmd):
 r=subprocess.run(cmd,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-2500:])
def render(project):
 generated=ROOT/'generated'/(project+'-clothed.mp4');original=ROOT/'clean'/(project+'-clean-body.mp4');normalized=OUT/(project+'-normalized.mp4')
 sh(['ffmpeg','-v','error','-y','-i',str(generated),'-vf',f'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30,trim=end_frame={FRAMES[project]},format=yuv420p','-an','-c:v','libx264','-preset','fast','-crf','18',str(normalized)])
 inserts=[(round(a*30),round(b*30),c) for a,b,c in INSERTS[project]];segs=[];at=0
 for a,b,c in inserts:
  if a>at:segs.append((at,a,None,normalized))
  segs.append((a,b,c,original));at=b
 if at<FRAMES[project]:segs.append((at,FRAMES[project],None,normalized))
 files=[]
 for n,(a,b,c,src) in enumerate(segs):
  dst=OUT/f'{project}-{n:02}.mp4';vf=f'trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS,'
  if c:vf+='crop='+':'.join(map(str,c))+','
  vf+='scale=720:1280,setsar=1,fps=30,settb=1/30,setpts=N/(30*TB),format=yuv420p'
  sh(['ffmpeg','-v','error','-y','-i',str(src),'-vf',vf,'-an','-c:v','libx264','-preset','fast','-crf','18','-r','30','-fps_mode','cfr','-video_track_timescale','30000',str(dst)]);files.append(dst)
 manifest=OUT/(project+'-concat.txt');manifest.write_text(''.join("file '"+str(f.resolve())+"'\n" for f in files))
 final=OUT/(project+'-clothed.mp4');sh(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(manifest),'-c','copy',str(final)]);print(str(final),flush=True)
if __name__=='__main__':
 import sys
 render(sys.argv[1])
