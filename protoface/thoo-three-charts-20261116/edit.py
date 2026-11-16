"""Three-chart explainer cards, native Mandarin dialogue and user-provided BGM."""
import argparse
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'output'
OUT.mkdir(exist_ok=True)
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
EN='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
import os
MUSIC=Path(os.environ.get('THOO_BGM', str(ROOT.parent.parent.parent/'upload'/'Trouble In My DMs(1).mp3')))

def source(n):
    edited=OUT/f'edited-{n:02d}.mp4'
    return edited if edited.exists() else OUT/f'scene-{n:02d}.mp4'

def prepare():
    timeline=json.loads((ROOT/'timeline.json').read_text())
    for key,parts in timeline.items():
        n=int(key)
        if parts==[[0,12]]:continue
        target=OUT/f'edited-{n:02d}.mp4'
        filters=[];labels=[]
        for i,(a,b) in enumerate(parts):
            filters.extend([f'[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}]',f'[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}]'])
            labels.append(f'[v{i}][a{i}]')
        filters.append(''.join(labels)+f'concat=n={len(parts)}:v=1:a=1[vc][ac]')
        filters.extend(['[vc]fps=24,tpad=stop_mode=clone:stop_duration=5[v]','[ac]apad[a]'])
        run(['ffmpeg','-y','-v','error','-i',str(OUT/f'scene-{n:02d}.mp4'),'-filter_complex',';'.join(filters),'-map','[v]','-map','[a]','-t','12','-c:v','libx264','-crf','17','-preset','fast','-c:a','pcm_s16le',str(target.with_suffix('.mov'))])
        # Keep a standard MP4 input while copying video without another encode.
        run(['ffmpeg','-y','-v','error','-i',str(target.with_suffix('.mov')),'-c:v','copy','-c:a','aac','-b:a','256k',str(target)])
PINK='#F7B9C5';GREEN='#B8E7CB';PURPLE='#D9C3F4'

def run(args):
    subprocess.run(args,check=True)

def font(size):
    return ImageFont.truetype(FONT,size)

def fit(draw,text,size,width):
    while draw.textlength(text,font=font(size))>width:
        size-=1
    return font(size)

def cards():
    for n in range(1,6):
        im=Image.new('RGBA',(720,1280),(0,0,0,0));d=ImageDraw.Draw(im)
        accent=[PINK,PINK,GREEN,PURPLE,PINK][n-1]
        d.rounded_rectangle((26,48,694,322),radius=25,fill=(31,16,29,235),outline=accent,width=2)
        d.text((686,13),'AI动漫二创',font=font(18),anchor='ra',fill='#E9DEE5',stroke_width=1,stroke_fill='#221323')
        if n==1:
            d.text((51,65),'T HOO HOO',font=font(45),fill=PINK)
            d.text((53,124),'洋娃娃形态 · 三榜小队长',font=font(26),fill='#F4EAF2')
            d.text((51,178),'三张榜单，怎么支持？',font=font(39),fill='white')
            d.text((53,255),'打开QQ音乐 → 搜索「檀健次」',font=font(27),fill='#F2DAE2')
        elif n<5:
            index=n-1
            label=['粉色任务','绿色任务','紫色任务'][n-2]
            d.text((52,64),f'0{index} / {label}',font=font(25),fill=accent)
            title=['Billboard Global No.1s','腾讯音乐 由你榜','QQ音乐 巅峰潮流榜'][n-2]
            d.text((51,105),title,font=fit(d,title,39,616),fill='white')
            song='Trouble In My DMs' if n<4 else 'Dead Reflex (intro)'
            d.text((53,164),'《'+song+'》',font=font(31),fill=accent)
            tags=[['做任务','攒积分','投歌曲'],['听歌','推荐','分享','榜单任务'],['听歌','收藏','评论','分享']][n-2]
            left=52;gap=12;width=(616-gap*(len(tags)-1))/len(tags)
            for text in tags:
                d.rounded_rectangle((left,218,left+width,262),radius=10,fill=accent)
                d.text((left+width/2,221),text,font=font(24),anchor='ma',fill='#2D1B2D')
                left+=width+gap
            note=['2026国际榜 · 以活动页面为准','让音乐陪伴你的日常','这一榜要换歌，别选错！'][n-2]
            d.text((53,279),note,font=font(22),fill='#E4D5DF')
        else:
            d.text((51,65),'三榜分清楚 · 快乐支持',font=font(35),fill='white')
            rows=[('01','Billboard', 'Trouble In My DMs',PINK),('02','由你榜','Trouble In My DMs',GREEN),('03','巅峰潮流榜','Dead Reflex (intro)',PURPLE)]
            for i,(num,title,song,color) in enumerate(rows):
                y=125+i*56
                d.rounded_rectangle((50,y+3,95,y+41),radius=9,fill=color)
                d.text((72,y+4),num,font=font(23),anchor='ma',fill='#2D1B2D')
                d.text((110,y+3),title,font=font(27),fill=color)
                d.text((665,y+6),song,font=font(24),anchor='ra',fill='white')
        # Keep the platform-rule note visible without crowding the chart cards.
        d.text((360,1234),'榜单任务与有效记录，以平台页面为准',font=font(20),anchor='ma',fill='white',stroke_width=1,stroke_fill='#271728')
        im.save(OUT/f'card-{n:02d}.png')
    montage=Image.new('RGB',(720,5*340),'#1B0C19')
    for n in range(1,6):
        im=Image.open(OUT/f'card-{n:02d}.png').crop((0,0,720,340))
        montage.paste(im,(0,(n-1)*340),im)
    montage.save(OUT/'cards_preview.jpg',quality=93)

def transcribe():
    from faster_whisper import WhisperModel
    model=WhisperModel('large-v3-turbo',device='cpu',compute_type='int8',download_root=os.environ.get('THOO_ASR_CACHE',str(OUT/'asr_model')),cpu_threads=8)
    result={}
    for n in range(1,6):
        data=subprocess.check_output(['ffmpeg','-v','error','-i',str(OUT/f'scene-{n:02d}.mp4'),'-f','f32le','-ac','1','-ar','16000','pipe:1'])
        segs,_=model.transcribe(np.frombuffer(data,np.float32),language='zh',beam_size=5,word_timestamps=True,vad_filter=False,condition_on_previous_text=False)
        result[str(n)]=[{'start':s.start,'end':s.end,'text':s.text,'words':[{'start':w.start,'end':w.end,'word':w.word} for w in s.words]} for s in segs]
        print(n,[(s['start'],s['end'],s['text']) for s in result[str(n)]],flush=True)
    (OUT/'transcript.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))

def inspect():
    sheet=Image.new('RGB',(5*216,5*408),'#251526');d=ImageDraw.Draw(sheet)
    for n in range(1,6):
        for j,t in enumerate([.6,3,5.8,8.3,10.8]):
            path=OUT/f'frame-{n}-{j}.jpg'
            run(['ffmpeg','-v','error','-y','-ss',str(t),'-i',str(OUT/f'scene-{n:02d}.mp4'),'-frames:v','1','-vf','scale=216:384',str(path)])
            sheet.paste(Image.open(path),(j*216,(n-1)*408+24))
            d.text((j*216+5,(n-1)*408+2),f'{n} / {t:.1f}s',font=font(17),fill='white')
    sheet.save(OUT/'contact_sheet.jpg',quality=92)

def audio():
    captions=json.loads((ROOT/'caption_timing.json').read_text())
    windows=json.loads((ROOT/'dialogue_windows.json').read_text())
    sr=48000
    for n in range(1,6):
        data=subprocess.check_output(['ffmpeg','-v','error','-i',str(source(n)),'-f','f32le','-ac','2','-ar',str(sr),'pipe:1'])
        a=np.frombuffer(data,np.float32).reshape(-1,2).copy();gain=np.zeros(len(a),np.float32)
        for start,end in windows[str(n)]:
            x=max(0,int(start*sr));y=min(len(a),int(end*sr));fade=min(1200,(y-x)//2)
            gain[x:y]=1;gain[x:x+fade]=np.linspace(0,1,fade);gain[y-fade:y]=np.linspace(1,0,fade)
        a*=gain[:,None]
        with wave.open(str(OUT/f'dialogue-{n:02d}.wav'),'wb') as f:
            f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes((np.clip(a,-1,1)*32767).astype('<i2').tobytes())
    data=subprocess.check_output(['ffmpeg','-v','error','-t','60','-i',str(MUSIC),'-af','loudnorm=I=-16:TP=-1.5:LRA=9','-f','f32le','-ac','2','-ar',str(sr),'pipe:1'])
    a=np.frombuffer(data,np.float32).reshape(-1,2).copy()[:60*sr]
    if len(a)<60*sr:a=np.pad(a,((0,60*sr-len(a)),(0,0)))
    gain=np.full(len(a),.62,np.float32)
    for c in captions:
        x=max(0,int((c['start']-.25)*sr));y=min(len(a),int((c['end']+.25)*sr));gain[x:y]=.18
    from scipy.ndimage import gaussian_filter1d
    control=gaussian_filter1d(gain[::480],4)
    gain=np.interp(np.arange(len(a)),np.arange(len(control))*480,control)
    a*=gain[:,None];a[:sr//3]*=np.linspace(0,1,sr//3)[:,None];a[-sr:]*=np.linspace(1,0,sr)[:,None]
    with wave.open(str(OUT/'specified_bgm.wav'),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes((np.clip(a,-1,1)*32767).astype('<i2').tobytes())

def tm(t):
    t=round(t*100);return f'{t//360000}:{t//6000%60:02d}:{t//100%60:02d}.{t%100:02d}'

def render():
    captions=json.loads((ROOT/'caption_timing.json').read_text())
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Dialogue,Noto Sans CJK SC,44,&H00FFFFFF,&H00FFFFFF,&H00211220,&H80180E18,-1,0,0,0,100,100,0,0,1,2.4,0.6,2,38,38,165,1
Style: Speaker,Noto Sans CJK SC,26,&H00D7C7F6,&H00FFFFFF,&H00211220,&H80180E18,0,0,0,0,100,100,0,0,1,1.5,0.4,2,40,40,280,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    lines=[header]
    for c in captions:
        text=c['text']
        # Explicit balanced wrapping, leaving the short speaker label above two lines.
        if len(text)>17:
            spots=[i+1 for i,ch in enumerate(text) if ch in '，！？，、' and 6<=i<len(text)-4]
            k=min(spots,key=lambda i:abs(i-len(text)/2)) if spots else len(text)//2
            text=text[:k]+r'\N'+text[k:]
        lines.append(f"Dialogue: 2,{tm(c['start'])},{tm(c['end'])},Dialogue,,0,0,0,,{text}")
        lines.append(f"Dialogue: 2,{tm(c['start'])},{tm(c['end'])},Speaker,,0,0,0,,{c['speaker']}")
    ass=OUT/'captions.ass';ass.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for n in range(1,6):
        target=OUT/f'normal-{n:02d}.mp4'
        if target.exists():continue
        run(['ffmpeg','-y','-v','error','-i',str(source(n)),'-i',str(OUT/f'dialogue-{n:02d}.wav'),'-i',str(OUT/f'card-{n:02d}.png'),
             '-filter_complex','[0:v]fps=24,scale=720:1280:force_original_aspect_ratio=increase:flags=lanczos,crop=720:1280,setsar=1[v];[v][2:v]overlay=0:0:format=auto,format=yuv420p[vo]',
             '-map','[vo]','-map','1:a:0','-af','loudnorm=I=-16:TP=-2:LRA=10,apad','-t','12','-c:v','libx264','-crf','19','-preset','fast','-c:a','aac','-ar','48000','-ac','2','-b:a','192k',str(target)])
    listing=OUT/'concat.txt';listing.write_text(''.join(f"file 'normal-{n:02d}.mp4'\n" for n in range(1,6)))
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(OUT/'clean.mp4')])
    final=OUT/'THooHoo_Three_Charts_BGM_60s.mp4'
    run(['ffmpeg','-y','-v','error','-i',str(OUT/'clean.mp4'),'-i',str(OUT/'specified_bgm.wav'),
         '-filter_complex',f'[0:v]ass={ass}[v];[0:a][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]',
         '-map','[v]','-map','[a]','-t','60','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-ar','48000','-movflags','+faststart',str(final)])
    print('FINAL',final,'BYTES',final.stat().st_size,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','cards','transcribe','inspect','audio','render']);globals()[p.parse_args().action]()
