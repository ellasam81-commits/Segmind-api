from pathlib import Path
from PIL import Image,ImageDraw
import subprocess,json,io
ROOT=Path(__file__).resolve().parent;results=[];sheet=Image.new('RGB',(1080,640))
for i in range(1,5):
 r=json.load(open(ROOT/'output'/f'report-{i}.json'));p=ROOT/'output'/r['output'];source=ROOT.parent/'upload'/r['source']
 q=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]));v=next(s for s in q['streams'] if s['codec_type']=='video')
 assert v['profile']=='Main' and v['level']==40 and v['pix_fmt']=='yuv420p' and v['avg_frame_rate']=='30/1' and v['time_base']=='1/30000'
 assert int(v['nb_frames'])==r['frames'] and abs(float(q['format']['duration'])-r['duration'])<.04
 def audiohash(path):return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-c','copy','-f','hash','-hash','sha256','-']).decode().strip()
 same=audiohash(p)==audiohash(source);assert same
 subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],check=True)
 text=(ROOT/'output'/f'ending-{i}.ass').read_text();assert not any(t in text for t in ['芒果','预约','下载','http','打开','点击'])
 results.append({'output':r['output'],'duration':q['format']['duration'],'size':q['format']['size'],'frame_count':v['nb_frames'],'iPhone_encoding_checks':'passed','audio_bitstream_unchanged':same,'full_decode':'passed','endcard_external_cta_check':'passed'})
 if i>=3:
  times=[r['duration']-1.5] if i==3 else [r['duration']-4,r['duration']-1.5]
  for k,t in enumerate(times):
   b=subprocess.check_output(['ffmpeg','-v','error','-ss',str(t),'-i',str(p),'-frames:v','1','-vf','scale=360:640','-f','image2pipe','-vcodec','mjpeg','-'])
   pos=0 if i==3 else k+1;sheet.paste(Image.open(io.BytesIO(b)),(pos*360,0))
(ROOT/'review-34.jpg').write_bytes(b'')
sheet.save(ROOT/'review-34.jpg');(ROOT/'qa.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(results,ensure_ascii=False))
