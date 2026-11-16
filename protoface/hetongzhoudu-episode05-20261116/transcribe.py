from pathlib import Path
import json, subprocess
import numpy as np
from faster_whisper import WhisperModel
ROOT=Path(__file__).resolve().parent
m=WhisperModel('small',device='cpu',compute_type='int8',download_root=str(ROOT/'whisper'),cpu_threads=4)
out={}
for i in range(1,6):
 p=ROOT/'generated'/f'scene-{i:02}.mp4'
 samples=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-f','f32le','-ac','1','-ar','16000','pipe:1']),dtype=np.float32)
 segs,info=m.transcribe(samples,language='zh',beam_size=5,word_timestamps=True,vad_filter=True)
 out[str(i)]=[{'start':s.start,'end':s.end,'text':s.text,'words':[{'start':w.start,'end':w.end,'word':w.word} for w in s.words]} for s in segs]
 print(i,[(s['start'],s['end'],s['text']) for s in out[str(i)]],flush=True)
(ROOT/'transcript.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
