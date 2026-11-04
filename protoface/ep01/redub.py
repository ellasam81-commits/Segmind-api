"""Replace unreliable generated speech; edit existing pictures without regeneration."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import subprocess
import wave
from pathlib import Path

import numpy as np
import produce

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'corrected'
RATE = 48000


def run(args):
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-2500:])


def pcm(path):
    data = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
                                    '-ar', str(RATE), '-ac', '1', '-f', 'f32le', 'pipe:1'])
    return np.frombuffer(data, dtype='<f4').copy()


def write_wav(path, data):
    if data.ndim == 1:
        data = np.column_stack([data, data])
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes((np.clip(data, -.97, .97) * 32767).astype('<i2').tobytes())


def add(track, start, data, gain=1):
    offset = round(start * RATE)
    end = min(len(track), offset + len(data))
    if offset < 0 or end <= offset:
        raise ValueError('Audio cue outside timeline')
    track[offset:end] += data[:end-offset] * gain


def decode_packed_speech():
    path = ROOT / 'dialogue' / 'packed-speech.json'
    if not path.exists():
        return
    for name, entry in json.loads(path.read_text()).items():
        if name not in {f'line-{i:02}.mp3' for i in range(1, 8)}:
            raise ValueError('Unexpected speech filename')
        data = base64.b64decode(entry['data'], validate=True)
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Speech checksum mismatch')
        (ROOT / 'dialogue' / name).write_bytes(data)


def voice_track(manifest):
    track = np.zeros(60 * RATE)
    report = []
    for i, cue in enumerate(manifest['dialogue'], 1):
        data = pcm(ROOT / 'dialogue' / f'line-{i:02}.mp3')
        # Keep breath/consonant margins; remove the service's long silent tail.
        active = np.flatnonzero(np.abs(data) > .003)
        if not len(active):
            raise ValueError(f'Line {i} is silent')
        first = max(0, active[0] - round(.09 * RATE))
        last = min(len(data), active[-1] + round(.18 * RATE))
        data = data[first:last]
        duration = len(data) / RATE
        available = cue['end'] - cue['start']
        if duration > available + .12:
            raise ValueError(f'Line {i} needs {duration:.2f}s; retime before rendering')
        # Normalize each line once. Leave speech natural: no speed or pitch warp.
        rms = float(np.sqrt(np.mean(data * data)))
        data *= min(.14 / max(rms, 1e-6), .82 / max(float(np.max(np.abs(data))), 1e-6))
        fade = min(240, len(data)//4)
        data[:fade] *= np.linspace(0, 1, fade)
        data[-fade:] *= np.linspace(1, 0, fade)
        add(track, cue['start'], data)
        report.append({'line': i, 'text': cue['zh'], 'start': cue['start'],
                       'speech_end': round(cue['start'] + duration, 3),
                       'file_sha256': hashlib.sha256((ROOT/'dialogue'/f'line-{i:02}.mp3').read_bytes()).hexdigest()})
    write_wav(OUT / 'exact-dialogue-only.wav', track)
    return track, report


def effects(manifest):
    rng = np.random.default_rng(1301)
    timeline = np.zeros(60*RATE)

    def noise(duration, gain=.01, decay=0, grain=1):
        count = round(duration*RATE)
        if grain > 1:
            positions = np.arange(0, count+grain, grain)
            data = np.interp(np.arange(count), positions, rng.normal(0, 1, len(positions)))
        else:
            data = rng.normal(0, 1, count)
        data *= gain
        if decay:
            data *= np.exp(-np.arange(count)/RATE*decay)
        edge = min(round(.02*RATE), count//4)
        data[:edge] *= np.linspace(0, 1, edge)
        data[-edge:] *= np.linspace(1, 0, edge)
        return data

    # Quiet office air, then exterior wind, then hollow interior air.
    add(timeline, 0, noise(26.5, .0015, grain=55))
    add(timeline, 26.5, noise(17, .005, grain=200))
    add(timeline, 43.5, noise(16.5, .003, grain=120))
    # Paper / envelope / map, only on the existing actions.
    for start, duration in [(1.7,.45),(3.2,.35),(4.0,.3),(11.4,.7),(13.1,.9),
                            (15.1,.4),(20.0,.7)]:
        add(timeline, start, noise(duration, .013, grain=3))
    for start in [7.8,8.0,8.22,8.5,8.71,8.95,9.1]:
        add(timeline, start, noise(.045, .018, decay=65, grain=2))

    # Ordinary key / zip / latch. High-frequency ticks cannot be mistaken for knocks.
    for start, gain in [(24.7,.025),(34.7,.075),(39.2,.015)]:
        t=np.arange(round(.20*RATE))/RATE
        data=gain*(np.sin(2*np.pi*1850*t)+.35*np.sin(2*np.pi*2840*t))*np.exp(-t*36)
        add(timeline,start,data)
    add(timeline,39.3,noise(.32,.016,grain=3))
    # Long iron hinge and cold draft as the gate opens; no extra impact.
    t=np.arange(round(1.65*RATE))/RATE
    hinge=.014*np.sin(2*np.pi*(260*t+30*t*t))*np.sin(np.pi*t/1.65)**2
    add(timeline,36.1,hinge+noise(1.65,.008,grain=6))
    add(timeline,36.3,noise(2.0,.018,grain=160))
    # Soft shoe scuffs (different timbre from the plot's distinct six knocks).
    for start in [25.4,25.9,41.3,41.9,42.5,43.1,43.8,44.5,45.1]:
        add(timeline,start,noise(.16,.021,decay=15,grain=18))
    for i, start in enumerate(manifest['knocks']):
        t=np.arange(round(.72*RATE))/RATE
        hit=(.30 if i<3 else .39)*(np.sin(2*np.pi*90*t)+.32*np.sin(2*np.pi*177*t))*np.exp(-t*13)
        hit*=np.minimum(t/.004,1)
        add(timeline,start,hit)
        add(timeline,start+.11,hit*.18)
        add(timeline,start+.24,hit*.065)
    write_wav(OUT/'scripted-effects.wav',timeline)
    return timeline


def make_audio(manifest):
    OUT.mkdir(exist_ok=True)
    decode_packed_speech()
    speech, report = voice_track(manifest)
    foley = effects(manifest)
    clean = speech+foley
    write_wav(OUT/'dialogue-effects.wav', clean)
    # Subtle optional final score; clean export remains entirely music-free.
    t=np.arange(60*RATE)/RATE
    score=(.009*np.sin(2*np.pi*55*t)+.004*np.sin(2*np.pi*82.4*t))
    score*=np.minimum(t/3,1)*np.clip((54-t)/5,0,1)
    duck=np.ones(len(t))
    for cue in manifest['dialogue']:
        a=max(0,round((cue['start']-.12)*RATE));b=min(len(t),round((cue['end']+.1)*RATE));duck[a:b]=.18
    write_wav(OUT/'dialogue-effects-bgm.wav',clean+score*duck)
    (OUT/'audio-review.json').write_text(json.dumps({'native_generated_audio_used':False,
        'dialogue':report,'address_spoken_times':2,'knock_onsets_seconds':manifest['knocks'],
        'duration_seconds':60,'lip_sync':'Replacement speech; frame-accurate lip sync not verified.'},ensure_ascii=False,indent=2))


def render_first(source):
    run(['ffmpeg','-v','error','-y','-filter_threads','1','-i',str(source),
         '-i',str(OUT/'dialogue-effects.wav'),'-map','0:v:0','-map','1:a:0',
         '-vf','fps=24,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1',
         '-t','15','-c:v','libx264','-preset','veryfast','-crf','19','-threads','2',
         '-c:a','aac','-b:a','192k','-movflags','+faststart',str(OUT/'episode01-part01-redubbed-480p.mp4')])


def render_full(sources):
    for i, source in enumerate(sources, 1):
        run(['ffmpeg','-v','error','-y','-filter_threads','1','-i',str(source),'-an',
             '-vf','fps=24,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2,setsar=1,tpad=stop_mode=clone:stop_duration=0.4',
             '-t','15','-c:v','libx264','-preset','veryfast','-crf','19','-threads','2',str(OUT/f'picture-{i:02}.mp4')])
    (OUT/'concat.txt').write_text(''.join(f"file 'picture-{i:02}.mp4'\n" for i in range(1,5)))
    run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',str(OUT/'concat.txt'),
         '-i',str(OUT/'dialogue-effects.wav'),'-map','0:v:0','-map','1:a:0','-c:v','copy',
         '-c:a','aac','-b:a','192k','-t','60','-movflags','+faststart',str(OUT/'episode01-corrected-clean-480p.mp4')])
    manifest=json.loads((ROOT/'episode.json').read_text())
    produce.OUT=OUT
    produce.captions(manifest)
    run(['ffmpeg','-v','error','-y','-filter_threads','1',
         '-i',str(OUT/'episode01-corrected-clean-480p.mp4'),'-i',str(OUT/'dialogue-effects-bgm.wav'),
         '-map','0:v:0','-map','1:a:0','-vf',f"ass={OUT/'episode01.ass'}",'-t','60',
         '-c:v','libx264','-preset','veryfast','-crf','19','-threads','2','-pix_fmt','yuv420p',
         '-c:a','aac','-b:a','192k','-movflags','+faststart',str(OUT/'episode01-corrected-bilingual-480p.mp4')])
    for i in range(1,5):
        run(['ffmpeg','-v','error','-y','-i',str(OUT/f'picture-{i:02}.mp4'),
             '-ss',str((i-1)*15),'-i',str(OUT/'dialogue-effects.wav'),'-map','0:v:0','-map','1:a:0',
             '-t','15','-c:v','copy','-c:a','aac','-b:a','192k','-movflags','+faststart',str(OUT/f'part-{i:02}-clean-480p.mp4')])
    for filename in ['episode01-corrected-clean-480p.mp4','episode01-corrected-bilingual-480p.mp4']:
        info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height','-of','json',str(OUT/filename)]))
        if abs(float(info['format']['duration'])-60)>.1:
            raise ValueError('Full episode duration differs from sixty seconds')
        if not any(x.get('width')==854 and x.get('height')==480 for x in info['streams']):
            raise ValueError('Full episode canvas differs from requested 480p')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--checkpoint',type=Path)
    parser.add_argument('--first',type=Path)
    args=parser.parse_args()
    manifest=json.loads((ROOT/'episode.json').read_text())
    make_audio(manifest)
    if args.first:
        render_first(args.first)
    if args.checkpoint:
        render_full([args.checkpoint/f'native-{i:02}.mp4' for i in range(1,5)])
