"""Local dialogue timing, original backing track, captions and iPhone MP4 export."""
import argparse
import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
OUT.mkdir(exist_ok=True)
REQ = json.loads((ROOT / 'request.json').read_text())
FONT = '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'


def command(args):
    subprocess.run(args, check=True)


def transcribe():
    from faster_whisper import WhisperModel
    model = WhisperModel('small', device='cpu', compute_type='int8',
                         download_root='/workspace/scratch/bacd4b9d7682/asr_model', cpu_threads=4)
    transcript = {}
    for n in range(1, 6):
        source = OUT / f'scene-{n:02d}.mp4'
        data = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(source), '-f', 'f32le',
                                        '-ac', '1', '-ar', '16000', 'pipe:1'])
        segments, _ = model.transcribe(np.frombuffer(data, np.float32), language='zh', beam_size=5,
                                      word_timestamps=True, vad_filter=True)
        transcript[str(n)] = [{'start': s.start, 'end': s.end, 'text': s.text,
                              'words': [{'start': w.start, 'end': w.end, 'word': w.word} for w in s.words]}
                             for s in segments]
        print(n, [(s['start'], s['end'], s['text']) for s in transcript[str(n)]], flush=True)
    (OUT / 'transcript.json').write_text(json.dumps(transcript, ensure_ascii=False, indent=2))


def inspect():
    sheet = Image.new('RGB', (5 * 216, 5 * 408), '#241a21')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT, 17)
    report = []
    for n in range(1, 6):
        source = OUT / f'scene-{n:02d}.mp4'
        metadata = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                                       '-show_format', '-of', 'json', str(source)]))
        streams = metadata['streams']
        video = next(s for s in streams if s['codec_type'] == 'video')
        assert any(s['codec_type'] == 'audio' for s in streams), f'No audio in scene {n}'
        duration = float(metadata['format']['duration'])
        assert 11.5 <= duration <= 12.5, (n, duration)
        report.append({'scene': n, 'width': video['width'], 'height': video['height'], 'duration': duration,
                       'audio': True, 'bytes': source.stat().st_size})
        for j, moment in enumerate([0.5, 3, 5.8, 8.2, 11]):
            frame = OUT / f'frame-{n}-{j}.jpg'
            command(['ffmpeg', '-v', 'error', '-y', '-ss', str(moment), '-i', str(source),
                     '-frames:v', '1', '-vf', 'scale=216:384', str(frame)])
            sheet.paste(Image.open(frame), (j * 216, (n-1) * 408 + 24))
            draw.text((j * 216 + 5, (n-1) * 408 + 2), f'{n} / {moment:.1f}s', fill='white', font=font)
    sheet.save(OUT / 'contact_sheet.jpg', quality=90)
    (OUT / 'media_checks.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


def backing():
    """Compose a soft original 100 BPM playful lounge-pop backing, no sampled song."""
    sr = 48000
    size = 60 * sr
    mix = np.zeros((size, 2), np.float64)
    random = np.random.default_rng(8191)
    beat = 0.6
    chords = [(53, 57, 60, 64), (52, 55, 59, 62), (57, 60, 64, 67), (55, 59, 62, 65)]

    def add(at, signal, amplitude=1, pan=0):
        start = round(at * sr)
        if start >= size:
            return
        take = min(len(signal), size-start)
        signal = signal[:take] * amplitude
        mix[start:start+take, 0] += signal * math.sqrt((1-pan)/2)
        mix[start:start+take, 1] += signal * math.sqrt((1+pan)/2)

    def note(midi, duration, soft=False):
        t = np.arange(round(duration * sr)) / sr
        f = 440 * 2 ** ((midi-69)/12)
        decay = 1.8 if soft else 5.5
        envelope = np.minimum(t / 0.008, 1) * np.exp(-t * decay)
        return (np.sin(2*np.pi*f*t) + 0.22*np.sin(4*np.pi*f*t) + 0.07*np.sin(6*np.pi*f*t))*envelope

    for bar in range(25):
        base = bar * 4 * beat
        chord = chords[bar % 4]
        for midi in chord:
            add(base, note(midi+12, 2.35, True), 0.028, (midi-chord[0])/24-0.25)
        for b, midi in [(0, chord[0]-12), (1.5, chord[0]), (2.5, chord[0]-12)]:
            add(base+b*beat, note(midi, 0.45, True), 0.075)
        for b in (0, 2):
            t = np.arange(int(0.2*sr))/sr
            kick = np.sin(2*np.pi*(48*t + (105-48)*0.025*(1-np.exp(-t/0.025))))*np.exp(-t*25)
            add(base+b*beat, kick, 0.13)
        for b in (1, 3):
            t = np.arange(int(0.1*sr))/sr
            noise = random.standard_normal(len(t))
            snap = (noise-np.roll(noise, 1))*np.exp(-t*65)
            add(base+b*beat, snap, 0.016, 0.15)
        for eighth in range(8):
            t = np.arange(int(0.045*sr))/sr
            noise = random.standard_normal(len(t))
            hat = (noise-np.roll(noise, 1))*np.exp(-t*110)
            add(base+eighth*beat/2, hat, 0.006 if eighth%2 else 0.008, -0.35)
        if bar % 2 == 0:
            for b, midi in [(0.5, chord[2]+24), (1.5, chord[1]+24), (3, chord[3]+24)]:
                add(base+b*beat, note(midi, 0.65), 0.025, 0.3)
    captions = json.loads((OUT / 'caption_timing.json').read_text())
    envelope = np.full(size, 0.62)
    for c in captions:
        left = max(0, int((c['start']-0.18)*sr))
        right = min(size, int((c['end']+0.22)*sr))
        envelope[left:right] = 0.30
    from scipy.ndimage import gaussian_filter1d
    envelope = gaussian_filter1d(envelope[::480], 3)
    envelope = np.interp(np.arange(size), np.arange(len(envelope))*480, envelope)
    mix *= 2.0 * envelope[:, None]
    mix[:sr] *= np.linspace(0, 1, sr)[:, None]
    mix[-sr*2:] *= np.linspace(1, 0, sr*2)[:, None]
    with wave.open(str(OUT/'original_backing.wav'), 'wb') as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(sr)
        f.writeframes((np.clip(mix, -1, 1)*32767).astype('<i2').tobytes())


def clean_audio():
    """Retain verified native dialogue, removing extra generated speech and repetition."""
    windows = json.loads((OUT/'dialogue_windows.json').read_text())
    sr = 48000
    for n in range(1, 6):
        data = subprocess.check_output(['ffmpeg','-v','error','-i',str(OUT/f'scene-{n:02d}.mp4'),
                                        '-f','f32le','-ac','2','-ar',str(sr),'pipe:1'])
        audio = np.frombuffer(data,np.float32).reshape(-1,2).copy()
        gain = np.zeros(len(audio),np.float32)
        for start,end in windows[str(n)]:
            a=max(0,int(start*sr)); b=min(len(gain),int(end*sr))
            fade=min(int(.025*sr),(b-a)//2)
            gain[a:b]=1
            gain[a:a+fade]=np.linspace(0,1,fade)
            gain[b-fade:b]=np.linspace(1,0,fade)
        audio*=gain[:,None]
        with wave.open(str(OUT/f'clean_audio-{n:02d}.wav'),'wb') as f:
            f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr)
            f.writeframes((np.clip(audio,-1,1)*32767).astype('<i2').tobytes())


def ass_time(seconds):
    total = round(seconds*100)
    return f'{total//360000}:{total//6000%60:02d}:{total//100%60:02d}.{total%100:02d}'


def render():
    captions = json.loads((OUT/'caption_timing.json').read_text())
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 720
PlayResY: 1280
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Dialogue,Noto Sans CJK SC,46,&H00FFFFFF,&H00FFFFFF,&H00211220,&H80180E18,-1,0,0,0,100,100,0,0,1,2.2,0.6,2,42,42,180,1
Style: Title,Noto Sans CJK SC,38,&H00E9EFFB,&H00FFFFFF,&H00422636,&H00000000,-1,0,0,0,100,100,0,0,1,1.3,0.3,7,36,36,110,1
Style: Label,Noto Sans CJK SC,23,&H00E5DDE8,&H00FFFFFF,&H00422636,&H00000000,0,0,0,0,100,100,0,0,1,1,0,7,36,36,153,1
Style: End,Noto Sans CJK SC,42,&H00FFFFFF,&H00FFFFFF,&H00332635,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,38,38,210,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
'''
    lines = [header,
             'Dialogue: 1,0:00:00.00,0:00:02.80,Title,,0,0,0,,大哥，我不是氛围灯！',
             r'Dialogue: 1,0:00:00.00,0:01:00.00,Label,,0,0,0,,{\an9\pos(687,34)}AI动漫二创']
    for c in captions:
        lines.append(f"Dialogue: 2,{ass_time(c['start'])},{ass_time(c['end'])},Dialogue,,0,0,0,,{c['text']}")
    lines += [r'Dialogue: 2,0:00:57.20,0:01:00.00,End,,0,0,0,,{\pos(360,978)\fad(200,0)}嘴上说只听一首',
              r'Dialogue: 2,0:00:57.20,0:01:00.00,End,,0,0,0,,{\pos(360,1028)\fad(200,0)}手已经点了收藏',
              r'Dialogue: 2,0:00:57.20,0:01:00.00,End,,0,0,0,,{\pos(360,1098)\fs25\fad(200,0)}今日歌单 · 檀健次',
              r'Dialogue: 2,0:00:57.20,0:01:00.00,End,,0,0,0,,{\pos(360,1136)\fs26\fad(200,0)}Trouble In My DMs']
    ass = OUT/'captions.ass'
    ass.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    for n in range(1, 6):
        if (OUT/f'norm-{n:02d}.mp4').exists():
            continue
        command(['ffmpeg','-y','-v','error','-i',str(OUT/f'scene-{n:02d}.mp4'),
                 '-i',str(OUT/f'clean_audio-{n:02d}.wav'),'-map','0:v:0','-map','1:a:0',
                 '-vf','fps=24,scale=720:1280:force_original_aspect_ratio=increase:flags=lanczos,crop=720:1280,setsar=1,format=yuv420p',
                 '-af','aresample=async=1:first_pts=0,loudnorm=I=-17:TP=-2:LRA=11,apad',
                 '-t','12','-c:v','libx264','-preset','fast','-crf','19','-c:a','aac',
                 '-ar','48000','-ac','2','-b:a','192k',str(OUT/f'norm-{n:02d}.mp4')])
    playlist = OUT/'concat.txt'
    playlist.write_text(''.join(f"file 'norm-{n:02d}.mp4'\n" for n in range(1,6)))
    clean = OUT/'clean.mp4'
    command(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(playlist),'-c','copy',str(clean)])
    final = OUT/'THooHoo_Color_Doll_60s.mp4'
    video_filter = f"[0:v]drawbox=x=22:y=88:w=456:h=96:color=0x291021@0.52:t=fill:enable='lt(t,2.8)',drawbox=x=22:y=918:w=676:h=248:color=0x291021@0.82:t=fill:enable='gte(t,57.2)',ass={ass}[v];[0:a][1:a]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]"
    command(['ffmpeg','-y','-v','error','-i',str(clean),'-i',str(OUT/'original_backing.wav'),
             '-filter_complex',video_filter,'-map','[v]','-map','[a]','-t','60',
             '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',
             '-c:a','aac','-ar','48000','-b:a','192k','-movflags','+faststart',str(final)])
    print('FINAL',final,'BYTES',final.stat().st_size,flush=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('action',choices=['transcribe','inspect','backing','clean_audio','render'])
    globals()[p.parse_args().action]()
