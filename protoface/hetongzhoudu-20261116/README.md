# 何不同舟渡 · 小炭火上药记

Fan-made anime adaptation of the supplied medicine scene. Cast follows the supplied male portrait and flame-spirit artwork; visual style follows the supplied fourth video. This is fictional fan promotion, not official drama footage.

Four 12-second 9:16 Protoface MiniMax H3 scenes, native Mandarin dialogue, locally verified captions and a 3.5-second end card. A single reference image is made with GPT Image 2 through Protoface. Reference cap 10 credits; animation cap 60 credits; no automatic paid replacement requests. API key stays in the repository secret PROTOFACE_API_KEY. Existing drama workflows are untouched.

The branch-specific workflow runs only when request.json changes. Its phase selects cast or video. Same payloads use stable idempotency keys. Generated clips and metadata are retained as workflow artifacts. After downloading scene-01.mp4 through scene-04.mp4 into this directory, run python assemble.py with FFmpeg and Noto CJK fonts installed. The optional caption-timing.json overrides planned timings based on the produced dialogue.
