# 挂播，不是挂起来！ 日漫小剧场

Adult Japanese anime male lead and T Hoo Hoo. Generated via GitHub Actions and Protoface on 2026-11-15, with original fictional Mandarin character voices.

The completed cast image cost 22 credits; three 12-second H3 segments cost 15 each (67 total). No replacement generations were submitted. Cast workflow 43690723987; video workflow 43690917443.

Final edit removes an unsolicited line from the first 1.75 seconds of segment 3. Finished video is 34.25 seconds with timed Chinese subtitles, song-title end card, and fan-fiction label. H3 source is 864×480; the final 1280×720 export scales the source and adds readable text, not native HD detail. No artist recording is embedded.

To reproduce the offline edit, download the video workflow artifact into `hangbo-anime-output`, copy `captions.json` into that output folder, then run `python protoface/hangbo-anime-20261115/assemble.py hangbo-anime-output`. Requires FFmpeg with libass and Noto Sans CJK SC fonts. This step makes no provider calls.

Generation runs only when this branch's request.json changes. Stable idempotency keys and live price checks protect each cast/scene request. The 22-credit cast and 45-credit video phase ceilings are enforced. API key remains in repository Actions secrets. Existing drama and tutorial projects are untouched.
