import asyncio,base64,json,pathlib,subprocess,os,urllib.request
root=pathlib.Path("fan-theater/yarn-post")
out=root/"audio"
out.mkdir(exist_ok=True)
lines=["玫瑰姐姐，快给我贴邮票！我要去小炭火家！","地址写哪儿？","糟了，我只写了歌名……","这封信倒是能先寄。打开音乐活动页，找到檀健次这首歌。","我懂了！做由你任务和专属任务，再把积分用来推荐歌曲。","对，记得留好截图。活动到十一月二十日中午十二点。","那我们什么时候出发呀？","截榜后，按组织者公布的细则上传截图，审核后参加抽奖。","原来要等抽奖呀！那我先去听歌，箱盖给我留条缝！"]
cast=[0,1,0,1,0,1,0,1,0]
async def edge():
    import edge_tts
    for i,line in enumerate(lines):
        v=["zh-CN-XiaoyiNeural","zh-CN-XiaoxiaoNeural"][cast[i]]
        await asyncio.wait_for(edge_tts.Communicate(line,v,rate="+8%",pitch=["+9Hz","-8Hz"][cast[i]]).save(f"/tmp/v{i}.mp3"),10)
try:
    asyncio.run(edge())
except Exception:
    subprocess.run(["python","-m","pip","install","-q","piper-tts==1.3.0"],check=True)
    base="https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx"
    for suffix in ["",".json"]:
        subprocess.run(["curl","-fLsS","--retry","2",base+suffix,"-o","/tmp/cn.onnx"+suffix],check=True)
    from piper import PiperVoice,SynthesisConfig
    import wave
    voice=PiperVoice.load("/tmp/cn.onnx")
    for i,line in enumerate(lines):
        with wave.open(f"/tmp/v{i}.wav","wb") as wf:
            voice.synthesize_wav(line,wf,syn_config=SynthesisConfig(length_scale=[.95,1.02][cast[i]]))
        pitch=[1.09,.98][cast[i]]
        subprocess.run(["ffmpeg","-y","-v","error","-i",f"/tmp/v{i}.wav","-af",f"asetrate={int(22050*pitch)},aresample=24000","-b:a","56k",f"/tmp/v{i}.mp3"],check=True)
for i in range(len(lines)):
    (out/f"{i}.txt").write_text(base64.b64encode(pathlib.Path(f"/tmp/v{i}.mp3").read_bytes()).decode())
