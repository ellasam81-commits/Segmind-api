"""Reconstruct the existing supplied-song stem for the repaired silent action."""
from pathlib import Path
from scipy.io import wavfile
src=Path(__file__).resolve().parent.parent/'hetongzhoudu-mask/mix_soundtrack.py'
code=src.read_text().split('fx=np.zeros')[0]
ns={'__file__':str(src)};exec(compile(code,str(src),'exec'),ns)
music=ns['music'];rate=ns['RATE']
# Same two already-approved cuts, expressed in original 45-second time.
a=round(18.4*rate);b=round((581/30)*rate);c=round((847/30)*rate);d=round(29.5*rate)
import numpy as np
out=np.concatenate([music[:a],music[b:c],music[d:]])
wavfile.write(Path(__file__).resolve().parent/'mask-music.wav',rate,out.astype(np.float32))
print(len(out)/rate)
