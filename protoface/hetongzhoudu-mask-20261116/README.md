# 面具之下 · 何不同舟渡粉丝原创动漫二创

45-second vertical fan short with Chinese dialogue, animated gold calligraphy, subtle transitions and a five-second end card. The supplied masked armor and face photographs guide the adult male anime design; the flame woman is 小炭火.

The factual basis is limited to the official synopses linked in sources.md. The mask reveal, 小炭火 scenes, arrows and all dialogue are original fan fiction, not verified novel or TV scenes. 小炭火 does not replace 南衣 in the original story.

## Generation
The existing GitHub Actions workflow uses Protoface for two character reference images and four 12-second clips. Recorded generation cost: 80 credits total, no paid retries. Only a request.json change triggers generation. Editing files do not trigger more generation.

## Postproduction
With scene-01.mp4 through scene-04.mp4 and cast-unmasked.png locally present, run prepare.py, render_story.py, then mix_soundtrack.py. The soundtrack script reads the user-supplied upload/幻火.mp3 from the parent directory; music and generated media are not committed to this public repository. FFmpeg, NumPy, SciPy and Noto Sans CJK SC are required. Ma Shan Zheng is fetched from its official font repository if absent.

The edit removes unrelated generated speech, uses a close-up to hide inconsistent mask handling, preserves the actual comic reply, and uses modest timing adjustment. Both characters remain fully dressed in this episode. Captions follow the retained dialogue. Music ducks for dialogue; original Foley remains, with only quiet mask and comic accents added.
