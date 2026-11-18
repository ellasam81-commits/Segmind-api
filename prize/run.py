from pathlib import Path
import concurrent.futures, json, os, subprocess, time
import requests
from PIL import Image, ImageDraw, ImageFont

repo = Path("output")
repo.mkdir(exist_ok=True)
model = "minimax/minimax-h3"
api = "https://api.protoface.com/v1"
headers = {"Authorization": "Bearer " + os.environ["PROTOFACE_API_KEY"]}
reference = "https://raw.githubusercontent.com/ellasam81-commits/Segmind-api/main/protoface/thoo-hoo-hangbo/storyboard_reference.jpg"
common = """Single continuous 16:9 premium chibi animation of the same two characters on a miniature apricot and lilac concert stage, a small curved prize booth with stage bulbs. Use reference for character identity only. Cute silver lavender haired chibi Tan Jianci in white stage jacket, red microphone, alongside tiny yellow T Hoo Hoo flame with blue oval eyes, pink cheeks, little hands and white boots. Attractive detailed soft toy materials, expressive faces, playful comic timing. No lettering, storyboards, speech bubbles or overlays. Native clean Mandarin speech exactly as directed. Young adult male cartoon speaking voice, high sweet mascot voice. No real voice imitation. Music barely audible. """
scenes = [
("小火苗的抽奖台","T Hoo Hoo peeks from a tiny gift box and asks: “我也能抽奖吗？” The chibi host kneels beside it, smiles and answers: “当然！十一月二十三号中午十二点开奖！”",["2026 年 11 月 23 日","中午 12:00 开奖"],"檀健次音乐助力奖励活动"),
("报名带齐三张图","T Hoo Hoo fans out three photo cards. Host counts them and says: “微博 ID、平台 ID、推荐积分页面，截图交到微信小程序抽奖助手。”",["① 微博 ID　② 平台 ID","③ 推荐积分页面"],"微信小程序「抽奖助手」提交审核"),
("先挑喜欢的小礼物","Mascot sniffs a tiny yellow crochet rose then holds up a signed photo and a bead bracelet. Host says: “黄玫瑰、印签、手串，你最想抽哪个？” Mascot reaches for all three, then hides its hands.",["Lv1　105 分　钩织黄玫瑰　105 份","Lv2　320 分　DISCOVERY 印签　13 份","Lv3　520 分　JCT 编珠手串　15 份"],"Lv1 至 Lv5 按单平台、单 ID 累计"),
("一千零五分怎么选？","Mascot lifts yellow gift box and asks: “一千零五分，只能选礼盒吗？” Host gently shakes head: “一到四档，挑你喜欢的！” Mascot hugs a tiny plush instead, eyes sparkling.",["Lv4　1005 分　Q 音超会礼盒　2 份","Lv5　1325 分　钩织 HOO／檀檀大头　7 份"],"达标后可选低档奖池"),
("围脖要怎么算？","The little flame wraps a yellow knitted scarf around itself until only its eyes show. Host laughs warmly and says: “第六档单独算，四个平台所有 ID 加起来，满一万分就能参加！”",["Lv6　10000 分　共 2 份","钩织渐变黄冬夜里的炭火围脖"],"四个平台所有 ID 的积分合计"),
("评论区还有一本！","Mascot rolls out a fashion magazine almost as large as itself. Host catches it: “还有一本杂志，在抽奖细则微博的评论区抽！” Mascot proudly gives a thumbs up.",["《Vogue Man》杂志　1 本","在抽奖细则微博评论区抽取"],"杂志单独抽取"),
("中奖以后别忘了","Host points to a gift tag. Mascot scribbles with an oversized pencil. Host says: “开奖后一天内，在抽奖助手填收件人、电话和地址。超时就算放弃哦！”",["开奖后 1 天内填收货信息","收货人 · 联系电话 · 收货地址"],"逾期视作放弃"),
("小火苗等你报喜","Mascot hugs a parcel, host waves: “按微博名单进邮寄群，备注登记手机号，进群后二十四小时内交中奖截图。邮费到付哦！”",["入群备注登记手机号","入群后 24 小时内交中奖截图","邮费自理 · 快递到付"],"寄出后群内分享运单号")]
def render(i, scene):
 title, action, lines, footer = scene
 payload = dict(prompt=common+action,reference=[reference],duration_seconds=9,quality="480p",aspect_ratio="16:9",generate_audio=True,enhance_prompt=False)
 if len(metadata.get("operations",{}))>1:payload["operation"]="video.general"
 r=requests.post(api+"/run/"+model,headers={**headers,"Idempotency-Key":f"fan-prize-20261118-v1-{i}"},json=payload,timeout=120)
 if not r.ok:raise RuntimeError(str(r.status_code)+" "+r.text[:240])
 rid=r.json()["id"]
 print("Accepted",i,rid,flush=True)
 for _ in range(240):
  state=requests.get(api+"/runs/"+rid+"/status",headers=headers,timeout=60).json()["status"]
  if state=="completed":break
  if state in ("failed","canceled"):raise RuntimeError(f"Scene {i}: {state}")
  time.sleep(5)
 result=requests.get(api+"/runs/"+rid,headers=headers,timeout=60).json()
 vid=result.get("video") or next(x["file"] for x in result["outputs"] if x["modality"]=="video")
 src=Path(f"/tmp/prize{i}.mp4")
 media=requests.get(vid["url"],timeout=150);media.raise_for_status();src.write_bytes(media.content)
 art=Image.new("RGB",(720,1280),"#35273f");d=ImageDraw.Draw(art)
 def write(y,txt,size,color,bold=False):
  font=ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSansCJK-"+("Bold" if bold else "Regular")+".ttc",size,index=2)
  while d.textlength(txt,font=font)>640:
   size-=1;font=ImageFont.truetype(font.path,size,index=2)
  d.text((360,y),txt,font=font,anchor="mm",fill=color)
 write(85,"檀健次音乐助力  ✦  粉丝小剧场",28,"#ffdc90")
 write(182,title,64,"#fff4df",True)
 d.rounded_rectangle((26,730,694,1144),radius=35,fill="#fff2dd")
 write(800,"抽 奖 说 明",28,"#795566",True)
 for k,line in enumerate(lines):write(900+(k-(len(lines)-1)/2)*73,line,38,"#3c2e42",True)
 write(1070,footer,26,"#784c58");write(1214,f"T Hoo Hoo   ✦   {i+1} / 8",25,"#ffe1a5")
 card=f"/tmp/card{i}.png";art.save(card)
 output=f"/tmp/segment{i}.mp4"
 subprocess.run(["ffmpeg","-loglevel","error","-y","-loop","1","-i",card,"-i",str(src),"-filter_complex","[1:v]scale=720:406,setsar=1[clip];[0:v][clip]overlay=0:274:shortest=1[v]","-map","[v]","-map","1:a:0","-t","9","-r","25","-c:v","libx264","-threads","2","-preset","veryfast","-pix_fmt","yuv420p","-c:a","aac","-ar","48000","-ac","2",output],check=True)
 return output
metadata=requests.get(api+"/models/"+model,headers=headers,timeout=60).json()
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 clips=list(pool.map(render,range(len(scenes)),scenes))
Path("/tmp/prize-list").write_text("".join(f"file '{p}'\n" for p in clips))
subprocess.run(["ffmpeg","-loglevel","error","-y","-f","concat","-safe","0","-i","/tmp/prize-list","-c","copy","-movflags","+faststart",str(repo/"Chibi_Prize_Theatre.mp4")],check=True)
