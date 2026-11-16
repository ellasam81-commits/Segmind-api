import subprocess,json,struct
from pathlib import Path
from PIL import Image
p=Path(__file__).resolve().parent/'output/XieQueshan_05_AreYouAVillain.mp4'
r=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)]))
summary=[{k:s.get(k) for k in ['codec_name','profile','level','width','height','pix_fmt','r_frame_rate','nb_frames','duration','sample_rate','channels']} for s in r['streams']]
print(summary,flush=True)
assert r['streams'][0]['nb_frames']=='1350'
canvas=Image.new('RGB',(1080,640))
for j,t in enumerate([2,4,12,14,20,29.7,33,35,39.7,41,42.7,44]):
 f=p.parent/f'final-{j}.png';subprocess.run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(p),'-frames:v','1','-vf','scale=180:320,format=rgb24',str(f)],check=True);canvas.paste(Image.open(f),((j%6)*180,(j//6)*320))
canvas.save(p.parent/'final-review.jpg')
subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],check=True)
with open(p,'rb') as f:
 boxes=[]
 while f.tell()<p.stat().st_size:
  offset=f.tell();head=f.read(8)
  if len(head)<8:break
  size,name=struct.unpack('>I4s',head);boxes.append((name.decode(),offset));f.seek(offset+size)
print(boxes[:6],flush=True)
assert next(o for n,o in boxes if n=='moov')<next(o for n,o in boxes if n=='mdat')
(p.parent/'qa.json').write_text(json.dumps({'streams':summary,'bytes':p.stat().st_size,'full_decode':'passed','mp4_boxes':boxes},indent=2))
