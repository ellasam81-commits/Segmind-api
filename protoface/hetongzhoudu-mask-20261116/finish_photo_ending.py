"""Use the exact existing soundtrack with the new two-photo end card."""
import argparse,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'output'
p=argparse.ArgumentParser()
p.add_argument('--audio-source',type=Path,default=OUT/'何不同舟渡_面具之下_动漫二创.mp4')
a=p.parse_args()
video=OUT/'何不同舟渡_面具之下_真人片尾_画面版.mp4'
dest=OUT/'何不同舟渡_面具之下_真人剧照片尾版.mp4'
subprocess.run(['ffmpeg','-y','-v','error','-i',str(video),'-i',str(a.audio_source),'-map','0:v:0','-map','1:a:0','-c','copy','-t','45','-movflags','+faststart',str(dest)],check=True)
print(dest)
