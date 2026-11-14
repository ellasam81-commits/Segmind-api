import asyncio,base64,pathlib,subprocess,wave
root=pathlib.Path("fan-theater/full-guide-outro")
(root/"audio").mkdir(exist_ok=True)
lines=["最后记住：由你积分先攒，再回活动页用；专属积分做完就可以推荐。活动到十一月二十日，争取前五名的国际推广机会。海内外的小炭火，一起支持檀健次的 Trouble In My DMs，让更多人听见他的音乐！","Remember: save UNI points, then use them on the event page. Exclusive points can be used after completing the tasks. The event ends on November twentieth. Let's aim for a top five place and the international promotion opportunity. Tan Jianci fans in China and around the world, support Trouble In My DMs and help more people hear his music!"]
async def go():
 import edge_tts
 for i,line in enumerate(lines):
  try:
   await asyncio.wait_for(edge_tts.Communicate(line,["zh-CN-XiaoxiaoNeural","en-US-JennyNeural"][i],rate="+5%",pitch="-8Hz").save(f"/tmp/outro{i}.mp3"),35)
  except Exception:
   subprocess.run(["python","-m","pip","install","-q","piper-tts==1.3.0"],check=True)
   name=["zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx","en/en_US/lessac/medium/en_US-lessac-medium.onnx"][i]
   for suff in ["",".json"]:
    subprocess.run(["curl","-fLsS","--retry","2","https://huggingface.co/rhasspy/piper-voices/resolve/main/"+name+suff,"-o",f"/tmp/m{i}.onnx"+suff],check=True)
   from piper import PiperVoice,SynthesisConfig
   v=PiperVoice.load(f"/tmp/m{i}.onnx")
   with wave.open(f"/tmp/outro{i}.wav","wb") as wf:v.synthesize_wav(line,wf,syn_config=SynthesisConfig(length_scale=1.02))
   subprocess.run(["ffmpeg","-y","-v","error","-i",f"/tmp/outro{i}.wav","-b:a","56k",f"/tmp/outro{i}.mp3"],check=True)
  (root/"audio"/f"{i}.txt").write_text(base64.b64encode(pathlib.Path(f"/tmp/outro{i}.mp3").read_bytes()).decode())
asyncio.run(go())
