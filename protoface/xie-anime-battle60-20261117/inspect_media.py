from pathlib import Path
import subprocess,json
from PIL import Image,ImageDraw
P=Path(__file__).resolve().parent;G=P/'generated';Q=P/'qa';Q.mkdir(exist_ok=True)
for src in sorted(G.glob('scene-*.mp4')):
 name=src.stem;r=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(src)]));print(name,r['format']['duration'],flush=True)
 canvas=Image.new('RGB',(900,660));d=ImageDraw.Draw(canvas)
 for j,t in enumerate([.15,1.2,2.3,3.4,4.5,5.5,6.5,7.5,8.5,9.5]):
  f=Q/f'{name}-{j}.png';subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(src),'-frames:v','1','-vf','scale=180:310:force_original_aspect_ratio=decrease,format=rgb24',str(f)],check=True);im=Image.open(f);x=(j%5)*180;y=(j//5)*330;canvas.paste(im,(x,y+20));d.text((x+4,y+3),f'{name} {t:.1f}s',fill='white')
 canvas.save(Q/(name+'.jpg'))
frames=sorted(G.glob('frame-*.png'))
if frames:
 canvas=Image.new('RGB',(300*3,560*2));d=ImageDraw.Draw(canvas)
 for j,p in enumerate(frames):
  im=Image.open(p);im.thumbnail((300,530));x=j%3*300;y=j//3*560;canvas.paste(im,(x,y+25));d.text((x+4,y+4),p.stem,fill='white')
 canvas.save(Q/'frames.jpg')
