# Story-only end card revision

The user supplied four completed videos and a Douyin notice identifying external-channel guidance in the picture. This revision removes the entire external-platform booking CTA, including platform names, search instructions and booking steps. It does not replace those instructions with homophones, disguised links or indirect off-platform directions. Recommendation restoration cannot be guaranteed.

## Replacement text

1. 小炭火上药记: 上药不难，难的是保持冷静。
2. 先把药瓶打开: 药瓶没开，心事先露馅了。
3. 将军你不是受伤了吗: 你以为，他只是受了伤？
4. 面具之下: 面具之下，藏着怎样的他？

All end cards retain 何不同舟渡 and 檀健次 饰 谢却山, with AI辅助创作 · 粉丝二创 · 非官方剧情 as the disclosure. The fourth retains the two supplied actor photographs. No new generative API calls are used.

## Rendering

Run `python3 rewrite_endcards.py 1` through `4`. The script uses the four local user uploads, clean final-shot images for films 1–2, the existing action-cast image for film 3, and the two supplied production photos for film 4. Required local folder layout follows the preceding project folders. These media assets and user music are not committed here.

Bodies, dialogue, original soundtracks and durations are retained. Original audio streams are copied without re-encoding. Video output uses H.264 Main level 4.0, 30 fps, yuv420p, a 30000-unit track time base and faststart. End card typography and fades are newly rendered to remove all prior booking instructions.
