"""Restore approved audio, captions and neutral animated endings to clothed edits."""
import importlib.util,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent;OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('cards',BASE/'douyin-endcards/rewrite_endcards.py');cards=importlib.util.module_from_spec(spec);spec.loader.exec_module(cards)
PROJECTS=['hetongzhoudu','hetongzhoudu-bottle','hetongzhoudu-guard'];BODIES=[1212,894,929];TOTAL=[1416,1098,1019]
def sh(c):
 r=subprocess.run(c,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-2000:])
def seconds(t):
 h,m,s=t.split(':');return int(h)*3600+int(m)*60+float(s)
def render(i):
 project=PROJECTS[i-1];frames=BODIES[i-1];total=TOTAL[i-1];src=ROOT/'restored'/f'{project}-clothed.mp4';audio=BASE/'douyin-endcards/output'/cards.CONFIG[i-1]['output'];duration=frames/30
 source_ass=BASE/project/'output'/('story.ass' if i==3 else 'wordart_v3.ass');lines=[]
 for line in source_ass.read_text().splitlines():
  if line.startswith('Dialogue:'):
   p=line.split(',',9)
   if seconds(p[1])>=duration-.01:continue
   if seconds(p[2])>duration:p[2]=cards.tm(duration)
   line=','.join(p)
   if '芒果' in line or '预约' in line:continue
   line=line.replace('粉丝二创 · 非正片','AI辅助创作 · 粉丝二创').replace('粉丝原创 · 非官方剧情','AI辅助创作 · 粉丝二创')
  lines.append(line)
 ass=OUT/f'body-{i}.ass';ass.write_text('\n'.join(lines)+'\n')
 # Match original body frame count and preserve every existing audio sample.
 p=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(src)]));v=next(x for x in p['streams'] if x['codec_type']=='video');actual=float(v.get('duration',duration));ratio=duration/actual
 body=OUT/f'body-{i}.mp4';vf=f"setpts={ratio:.10f}*(PTS-STARTPTS),scale=720:1280:force_original_aspect_ratio=increase:out_range=tv,crop=720:1280,setsar=1,fps=30,tpad=stop_mode=clone:stop_duration=0.2,trim=end_frame={frames},ass=filename='{ass}':fontsdir='{cards.FONT}',settb=1/30,setpts=N/(30*TB),fps=30,format=yuv420p"
 sh(['ffmpeg','-v','error','-y','-i',str(src),'-i',str(audio),'-vf',vf,'-map','0:v','-map','1:a','-c:v','libx264','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-r','30','-fps_mode','cfr','-enc_time_base:v','1:30','-video_track_timescale','30000','-c:a','copy','-t',str(total/30),str(body)])
 bg=ROOT/'refs/standing-clothed.png' if i==3 else OUT/f'clothed-end-{i}.png'
 if i<3:sh(['ffmpeg','-v','error','-y','-sseof','-0.1','-i',str(src),'-frames:v','1',str(bg)])
 # Reuse already-reviewed title animation, with clean clothed background and original duration.
 cards.OUT=OUT;cards.CONFIG[i-1]['source']=str(body);cards.CONFIG[i-1]['background']=str(bg);cards.CONFIG[i-1]['output']=f'{i:02}_'+cards.CONFIG[i-1]['title']+'_穿衣修订版.mp4';cards.render(i)
 (OUT/f'wardrobe-report-{i}.json').write_text(json.dumps({'edited_input_duration':actual,'approved_body_duration':duration,'timing_ratio':ratio,'audio_source':str(audio),'audio_copied':True},ensure_ascii=False,indent=2))
if __name__=='__main__':
 import sys
 render(int(sys.argv[1]))
