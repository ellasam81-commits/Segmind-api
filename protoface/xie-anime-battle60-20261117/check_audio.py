from pathlib import Path
import subprocess,json,numpy as np
from faster_whisper import WhisperModel
p=Path('battle60/generated');m=WhisperModel('small',device='cpu',compute_type='int8',cpu_threads=4,download_root='episode05/whisper');out={}
for n in [f'scene-{i:02}' for i in range(1,7)]:
 a=np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(p/(n+'.mp4')),'-ar','16000','-ac','1','-f','f32le','pipe:1']),dtype=np.float32)
 seg,info=m.transcribe(a,beam_size=5,vad_filter=True);out[n]=[{'start':s.start,'end':s.end,'text':s.text} for s in seg];print(n,out[n],flush=True)
(p/'audio-check.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
