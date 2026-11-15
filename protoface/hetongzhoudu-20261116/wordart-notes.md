# Word art and reservation edit

Renders the existing four edited animation clips with 8-frame crossfades and aligned Mandarin subtitles. Adds a 6.8-second outro with staggered gold brush lettering, a light sweep, drifting embers, a soft original bell phrase, and a Mango TV reservation CTA.

Run `python3 polish_wordart.py` after the original `assemble.py` has produced `output/normalized-01.mp4` through `normalized-04.mp4`. Requires FFmpeg with libass, Noto Sans CJK SC, and Python 3. Ma Shan Zheng is downloaded from the official Google Fonts repository if missing.

This edit does not invoke Protoface or change request.json.

Official series page checked on 2026-11-15: https://www.mgtv.com/h/832113.html
Official Mango TV upcoming listing with reservation: https://www.mgtv.com/h/800038.html
Font source: https://github.com/googlefonts/mashanzheng
