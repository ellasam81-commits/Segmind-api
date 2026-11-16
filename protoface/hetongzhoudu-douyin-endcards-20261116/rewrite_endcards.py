"""Replace external-platform promotional end cards with story-only captions."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent;OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
FONT=BASE/'hetongzhoudu-mask/fonts'
CONFIG=[
 {'title':'小炭火上药记','source':'何不同舟渡_小炭火上药记_配乐音效版(3).mp4','tail':6.8,'hook':'上药不难，难的是保持冷静。','background':str(ROOT/'clean-end-1.png'),'output':'01_小炭火上药记_剧情片尾版.mp4'},
 {'title':'先把药瓶打开','source':'何不同舟渡_先把药瓶打开_配乐音效版(3).mp4','tail':6.8,'hook':'药瓶没开，心事先露馅了。','background':str(ROOT/'clean-end-2.png'),'output':'02_先把药瓶打开_剧情片尾版.mp4'},
 {'title':'将军你不是受伤了吗','source':'何不同舟渡_将军你不是受伤了吗_动漫二创(2).mp4','tail':3,'hook':'你以为，他只是受了伤？','background':str(BASE/'hetongzhoudu-guard/action-cast.png'),'output':'03_将军你不是受伤了吗_剧情片尾版.mp4'},
 {'title':'面具之下','source':'XieQueshan_iPhone(4).mp4','tail':5,'hook':'面具之下，藏着怎样的他？','background':None,'output':'04_面具之下_剧情片尾版.mp4'}]
def tm(t):
 q=round(t*100);return f'{q//360000}:{q//6000%60:02}:{q//100%60:02}.{q%100:02}'
def render(i):
 c=CONFIG[i-1];src=BASE/'upload'/c['source']
 if i in [1,2] and not Path(c['background']).is_file():
  project='hetongzhoudu' if i==1 else 'hetongzhoudu-bottle'
  clean=BASE/project/'output/normalized-04.mp4'
  clean_duration=float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(clean)]))['format']['duration'])
  subprocess.run(['ffmpeg','-v','error','-y','-ss',str(clean_duration-.08),'-i',str(clean),'-frames:v','1',c['background']],check=True)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(src)]));v=next(s for s in probe['streams'] if s['codec_type']=='video')
 total_frames=round(float(probe['format']['duration'])*30);tail_frames=round(c['tail']*30);body_frames=total_frames-tail_frames;body=body_frames/30;end=total_frames/30;fade=.3
 header='''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
ScaledBorderAndShadow: yes
WrapStyle: 0
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Art,Ma Shan Zheng,105,&H007DD8FF,&H000000FF,&H00274464,&H80000000,0,0,0,0,100,100,0,0,1,0.7,0.5,5,0,0,0,1
Style: Text,Noto Sans CJK SC,34,&H00E9F2FF,&H000000FF,&H001C1713,&H80000000,0,0,0,0,100,100,1,0,1,0.8,0,5,0,0,0,1
Style: Shape,Noto Sans CJK SC,20,&H00000000,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
 ev=[]
 def e(a,b,style,text,layer=0):ev.append(f'Dialogue: {layer},{tm(a)},{tm(b)},{style},,0,0,0,,{text}')
 for j in range(32):
  opacity=.08+.84*(j/31)**1.3;alpha=round(255*(1-opacity));y=j*40
  e(body-.12,end,'Shape',r'{\an7\pos(0,0)\p1\1c&H131C24&\alpha&H%02X&\fad(350,0)}'%alpha+f'm 0 {y} l 720 {y} 720 {y+40} 0 {y+40}',10)
 e(body+.05,end,'Text',r'{\fs32\move(360,752,360,732,0,300)\fad(230,180)}'+c['hook'],20)
 for j,ch in enumerate('何不同舟渡'):
  x=164+j*98;e(body+.15+j*.045,end,'Art',f'{{\\move({x},856,{x},832,0,330)\\blur4\\t(0,330,\\blur0)\\fad(230,200)}}'+ch,22)
 e(body+.28,end,'Text',r'{\pos(360,948)\fs40\fsp2\1c&H9DDCFF&\fad(230,180)}檀健次 饰 谢却山',20)
 e(body+.12,end,'Text',r'{\pos(360,1198)\fs20\fsp0\1c&HCFDDE6&\fad(230,180)}AI辅助创作 · 粉丝二创 · 非官方剧情',20)
 ass=OUT/f'ending-{i}.ass';ass.write_text(header+'\n'.join(ev)+'\n')
 source_range='pc' if v.get('color_range')=='pc' else 'tv'
 filters=[f'[0:v]scale=720:1280:force_original_aspect_ratio=increase:in_range={source_range}:out_range=tv,crop=720:1280,setsar=1,fps=30,trim=end_frame={body_frames},settb=1/30,setpts=PTS-STARTPTS,fps=30[body]']
 args=['-i',str(src)]
 def image_chain(index,duration,label):
  return f"[{index}:v]scale=1440:2560:force_original_aspect_ratio=increase:out_range=tv,crop=1440:2560,zoompan=z='min(zoom+0.00015,1.035)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=720x1280:fps=30,trim=duration={duration},settb=1/30,setpts=PTS-STARTPTS,fps=30,setsar=1,format=yuv420p[{label}]"
 if i<4:
  args+=['-loop','1','-framerate','30','-i',c['background']];filters.append(image_chain(1,c['tail']+fade,'card'))
 else:
  args+=['-loop','1','-framerate','30','-i',str(BASE/'upload/IMG_1883(2).jpeg'),'-loop','1','-framerate','30','-i',str(BASE/'upload/IMG_1869(2).jpeg')]
  filters+=[image_chain(1,3.1,'photo1'),image_chain(2,2.8,'photo2'),'[photo1][photo2]xfade=transition=fade:duration=0.6:offset=2.5,trim=duration=5.3,settb=1/30,setpts=PTS-STARTPTS,fps=30[card]']
 filters.append(f"[body][card]xfade=transition=fade:duration={fade}:offset={body-fade},ass=filename='{ass}':fontsdir='{FONT}',fps=30,tpad=stop_mode=clone:stop_duration=0.04,trim=end_frame={total_frames},settb=1/30,setpts=N/(30*TB),format=yuv420p[v]")
 dst=OUT/c['output']
 cmd=['ffmpeg','-y','-v','error',*args,'-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[v]','-map','0:a:0','-c:v','libx264','-threads','3','-preset','fast','-crf','18','-profile:v','main','-level:v','4.0','-maxrate','8000k','-bufsize','16000k','-color_range','tv','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-r','30','-fps_mode','cfr','-enc_time_base:v','1:30','-video_track_timescale','30000','-c:a','copy','-t',str(end),'-movflags','+faststart',str(dst)]
 r=subprocess.run(cmd,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-3500:])
 report={'title':c['title'],'source':c['source'],'output':c['output'],'hook':c['hook'],'duration':end,'body_duration':body,'tail_duration':c['tail'],'frames':total_frames,'external_platform_cta':False,'audio_stream_copied':True}
 (OUT/f'report-{i}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('index',type=int,choices=range(1,5));a=p.parse_args();render(a.index)
