from pathlib import Path
import subprocess,json
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parent;Q=P/'qa';Q.mkdir(exist_ok=True)
for slug in ['ltx','h3']:
 f=P/(slug+'.mp4');r=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(f)]));print(slug,[(s['codec_type'],s.get('width'),s.get('height'),s.get('duration')) for s in r['streams']],flush=True)
 for part in range(2):
  canvas=Image.new('RGB',(900,660));d=ImageDraw.Draw(canvas)
  for j in range(10):
   t=part*5+j*.5+.1;out=Q/f'{slug}-{part}-{j}.png';subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(f),'-frames:v','1','-vf','scale=180:310:force_original_aspect_ratio=decrease,format=rgb24',str(out)],check=True)
   im=Image.open(out);x=(j%5)*180;y=(j//5)*330;canvas.paste(im,(x,y+20));d.text((x+4,y+3),f'{slug} {t:.1f}s',fill='white')
  canvas.save(Q/f'{slug}-part{part}.jpg')
