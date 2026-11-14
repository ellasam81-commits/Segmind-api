import asyncio,base64,json,pathlib,subprocess,os,urllib.request
root=pathlib.Path("fan-theater/full-guide-en")
out=root/"audio"
out.mkdir(exist_ok=True)
lines=["Here is a full guide to Billboard Global Number Ones. You can participate through QQ Music, Kugou, Kuwo, or Bodian. These screen recordings show the process. Available tasks and entry points depend on your app.","Open your music app and search for Tan Jianci. Find the Billboard Global Number Ones event and open it. Scroll down to the button for earning points through tasks. The task section is separate from the song rankings.","There are two types of points. First, earn and save your UNI points, then use them on the Billboard event page after completing your tasks. Second, event exclusive points can be used to recommend a song as soon as you earn them.","To earn UNI points, open the Tencent Music UNI Chart. Tap the profile icon at the top right to find the task list. Choose tasks that award points and follow the instructions shown on your screen.","For listening tasks, enter the song page from the task and press play. Follow the required play count or listening duration. Then return to the task list, check that it is complete, and claim the reward if a claim button appears.","Sharing and recommending songs can also be tasks. Share as instructed and check your progress afterward. Complete the required recommendations. Recommending on the UNI Chart is a separate action from recommending on the Billboard event page.","Ads, browsing, or app downloads may also offer UNI points. Check the reward type first. Wait until the ad is finished. For downloads, check whether opening or trying the app is required. Return to the task page and confirm the points arrived.","This recording also shows exchanging UNI points for recommendation attempts. That spends your UNI points. If you want to save points for Billboard, do not exchange your entire balance. Complete the tasks you need, and keep the remaining points.","Coins provide another way to earn points. Open the coin center and do available listening or ad tasks. Then look for an option to exchange coins for UNI points. Check the rate, limits, and conditions before exchanging, and confirm your UNI point balance afterward.","If you already plan to buy the album, enter through the album link on the UNI Chart. Check that the purchase page offers bonus UNI points and that your purchase qualifies. The recording demonstrates the entry point. The page determines the reward. Stay within your budget.","After completing the UNI tasks, keep the points until you return to the Billboard event. Saving them until the end means finishing this round of tasks first. Also check when your points expire and when the event ends.","Return to Billboard and open the exclusive points tasks. Check the available ad, app download, song recommendation, or listening tasks. Options can vary by platform and account. Complete the requirements, claim the points, and use them to recommend your song.","Go back to the event song list. Find Trouble In My DMs by Tan Jianci and tap Recommend. Check the song title. Choose UNI points or exclusive points, enter the amount, and complete any verification. Look for the success message and check your remaining balance.","Remember: all four platforms can participate. Earn UNI points first, then use them on the event page. Exclusive points can be used after completing the tasks. Support the music and aim to stay in the top five. Rankings change, so check the live event page."]
cast=[1]*len(lines)
async def edge():
    import edge_tts
    for i,line in enumerate(lines):
        v=["zh-CN-XiaoyiNeural","en-US-JennyNeural"][cast[i]]
        await asyncio.wait_for(edge_tts.Communicate(line,v,rate="+5%",pitch=["+9Hz","-8Hz"][cast[i]]).save(f"/tmp/v{i}.mp3"),35)
try:
    asyncio.run(edge())
except Exception:
    subprocess.run(["python","-m","pip","install","-q","piper-tts==1.3.0"],check=True)
    base="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
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
