import asyncio,base64,json,pathlib,subprocess,os,urllib.request
root=pathlib.Path("fan-theater/full-guide")
out=root/"audio"
out.mkdir(exist_ok=True)
lines=["这是一份完整的公告牌全球第一活动教程。QQ音乐、酷狗、酷我、波点都可以参与。下面用你看到的录屏示范，具体入口和任务，以各平台当前页面为准。","先打开音乐软件，搜索檀健次。找到 Billboard Global No.1s 活动入口，点进去，再往下找到做任务得积分。不要只看歌曲排名，任务区也要打开。","先分清两种积分。第一种是由你积分，先做任务积攒，留到最后回活动页推荐。第二种是活动专属积分，做完对应任务后，就可以回去推荐歌曲。","先看由你积分怎么拿。进入腾讯音乐由你榜，点击右上角头像，打开任务页面。找到有积分奖励、自己能够完成的任务，再按页面指引逐项操作。","听歌任务，从任务入口进入歌曲页，点击播放。播放次数、时长和奖励，都按任务说明完成。做完返回任务页，检查有没有显示完成，有领取按钮就点击领取。","还有分享和推荐歌曲任务。按页面要求分享歌曲，再返回检查进度。推荐任务就按要求完成相应次数。注意，由你榜推荐和最后的公告牌推荐，是两个不同操作。","看广告、浏览或者下载应用，也可能有由你积分奖励。先看清楚奖励是不是由你积分，再按要求完成。看完广告要等结束，下载任务要看是否还要求打开或体验，最后回任务页核对到账。","录屏里也展示了兑换推荐次数的操作。这个操作会使用由你积分。为了最后用于公告牌推荐，不要顺手把积分全部换完。只做需要的任务，剩余积分先留着。","金币是另一条获取积分的路径。进入金币中心，做听歌、广告等任务，攒到金币后，再找兑换由你积分的入口。兑换前看清比例、次数和条件，换好再去核对由你积分余额。","如果本来就打算购买专辑，可以从由你榜里的专辑入口进入。先查看购买页面有没有赠送由你积分的说明，确认符合活动条件再购买。录屏只示范入口，赠送数量以页面为准，按自己的预算支持就好。","由你任务做完，积分到账后，先保留。这里说的留到最后，是先完成这一轮任务，再回公告牌活动页使用；同时注意积分有效期和活动截止时间。","接着回到公告牌活动，打开专属积分任务。查看当前提供的广告、下载应用、推荐歌曲或听歌任务。不同平台和账号的任务可能不一样，完成后领取，拿到专属积分就可以回去推荐。","回到活动歌曲列表，找到檀健次的 Trouble In My DMs，点击推荐。确认歌曲名称，选择由你积分或者专属积分，输入推荐数量，按提示完成验证。看到推荐成功，再核对积分变化。","最后记住：四个平台都能参与；由你积分先攒，再回活动页用；专属积分做完就可以推荐。一起支持好音乐，争取保持前五名。排名实时变化，实际名次以活动页面为准。"]
cast=[1]*len(lines)
async def edge():
    import edge_tts
    for i,line in enumerate(lines):
        v=["zh-CN-XiaoyiNeural","zh-CN-XiaoxiaoNeural"][cast[i]]
        await asyncio.wait_for(edge_tts.Communicate(line,v,rate="+5%",pitch=["+9Hz","-8Hz"][cast[i]]).save(f"/tmp/v{i}.mp3"),35)
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
