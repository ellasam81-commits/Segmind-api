import json, os, pathlib, tempfile, urllib.request
from faster_whisper import WhisperModel
api=urllib.request.Request("https://api.protoface.com/v1/runs/run_01M75G4XMZS6NWA0Y818VV5891",headers={"Authorization":"Bearer "+os.environ.pop("PROTOFACE_API_KEY")})
with urllib.request.urlopen(api, timeout=60) as r: url=json.load(r)["video"]["url"]
with tempfile.TemporaryDirectory() as td:
    path=pathlib.Path(td)/"scene.mp4"
    urllib.request.urlretrieve(url,path)
    model=WhisperModel("base",device="cpu",compute_type="int8",cpu_threads=3)
    segs,_=model.transcribe(str(path),language="zh",word_timestamps=True,beam_size=3,initial_prompt="积分，收工，活动榜，推荐。")
    print("DIALOGUE TIMINGS",json.dumps([[round(w.start,2),round(w.end,2),w.word] for s in segs for w in s.words],ensure_ascii=False),flush=True)
