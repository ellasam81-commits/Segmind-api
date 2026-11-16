# T Hoo Hoo 的三榜小任务

60-second vertical fan animation. The collectible color-changing doll is T Hoo Hoo; the male character wears the supplied black outfit and silver shoulder fringe. Five 12-second PROTOFACE / MiniMax H3 scenes were generated in workflow run 43880089531.

## Chart mapping

| Doll color | Chart | Song | On-screen actions |
|---|---|---|---|
| Pink | Billboard Global No.1s 2026 | Trouble In My DMs | Tasks, points, vote |
| Mint | 腾讯音乐由你榜 | Trouble In My DMs | Listen, recommend, share, chart tasks |
| Lavender | QQ音乐巅峰潮流榜 | Dead Reflex (intro) | Listen, favorite, comment, share |

This mapping follows the user's supplied poster. Current chart activity pages govern tasks and valid records. No rank, deadline, or guaranteed distribution claim is made.

## Editing

`timeline.json` removes extra generated speech together with its corresponding picture. `dialogue_windows.json` retains the native Mandarin lines. `caption_timing.json` contains their mapped final timestamps. The last frame of shorter edited scenes holds long enough to read the chart card.

The user's exact supplied Trouble In My DMs recording is used continuously for the first 60 seconds, with volume ducking during dialogue. That recording is intentionally not included in this public repository. Set `THOO_BGM` to a local, authorized audio file.

Place the five source clips from the workflow artifact in `output/scene-01.mp4` through `output/scene-05.mp4`. Install Python packages numpy, Pillow and scipy, FFmpeg with libass, and Noto CJK fonts. Then run:

```bash
export THOO_BGM=/path/to/authorized-bgm.mp3
python edit.py cards
python edit.py prepare
python edit.py audio
python edit.py render
```

The render has readable Chinese captions, three chart cards and a final mapping recap. It includes an AI fan-animation label. API credentials remain in GitHub Actions secrets. Re-editing these files does not trigger paid generation; only the request file triggers that workflow.
