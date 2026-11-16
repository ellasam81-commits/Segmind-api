"""Check frame accuracy, iPhone encoding, complete decode and retained dialogue audio."""
import json,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent;OUT=ROOT/'output'
NAMES=['01_小炭火上药记_穿衣修订版.mp4','02_先把药瓶打开_穿衣修订版.mp4','03_将军你不是受伤了吗_穿衣修订版.mp4','04_面具之下_动作修订版.mp4']
OLD=['01_小炭火上药记_剧情片尾版.mp4','02_先把药瓶打开_剧情片尾版.mp4','03_将军你不是受伤了吗_剧情片尾版.mp4']
EXPECTED=[1416,1098,1019,1283]
def digest(p):
 b=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-map','0:a','-c:a','copy','-f','adts','pipe:1']);return hashlib.sha256(b).hexdigest()
rows=[]
for i,n in enumerate(NAMES):
 p=OUT/n
 if not p.exists():continue
 q=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)]));v=next(x for x in q['streams'] if x['codec_type']=='video');a=next(x for x in q['streams'] if x['codec_type']=='audio')
 assert v['codec_name']=='h264' and v['profile']=='Main' and v['level']==40
 assert v['pix_fmt']=='yuv420p' and v['avg_frame_rate']=='30/1' and v['time_base']=='1/30000'
 assert v['width']==720 and v['height']==1280 and int(v['nb_read_frames'])==EXPECTED[i]
 assert a['codec_name']=='aac' and a['sample_rate']=='48000' and a['channels']==2
 assert abs(float(q['format']['duration'])-EXPECTED[i]/30)<.05
 subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','null','-'],check=True,capture_output=True)
 audio_match=None
 if i<3:
  audio_match=digest(p)==digest(BASE/'douyin-endcards/output'/OLD[i]);assert audio_match,'Original audio packets changed'
 row={'file':n,'duration':float(q['format']['duration']),'frames':int(v['nb_read_frames']),'profile':v['profile'],'level':v['level'],'pixel_format':v['pix_fmt'],'audio_original_exact_match':audio_match,'decode':'pass'};rows.append(row);print(json.dumps(row,ensure_ascii=False),flush=True)
(OUT/'validation.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
