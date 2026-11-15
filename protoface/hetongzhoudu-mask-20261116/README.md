# 面具之下 · 何不同舟渡粉丝原创动漫二创

45-second vertical fan short with Chinese dialogue, animated gold calligraphy, subtle transitions and a five-second end card. The supplied masked armor and face photographs guide the adult male anime design; the flame woman is 小炭火.

The factual basis is limited to the official synopses linked in sources.md. The mask reveal, 小炭火 scenes, arrows and all dialogue are original fan fiction, not verified novel or TV scenes. 小炭火 does not replace 南衣 in the original story.

## Generation
The existing GitHub Actions workflow uses Protoface for two character reference images and four 12-second clips. Recorded generation cost: 80 credits total, no paid retries. Only a request.json change triggers generation. Editing files do not trigger more generation.

## Postproduction
With scene-01.mp4 through scene-04.mp4 and cast-unmasked.png locally present, run prepare.py, render_story.py, then mix_soundtrack.py. The soundtrack script reads the user-supplied upload/幻火.mp3 from the parent directory; music and generated media are not committed to this public repository. FFmpeg, NumPy, SciPy and Noto Sans CJK SC are required. Ma Shan Zheng is fetched from its official font repository if absent.

The edit removes unrelated generated speech, uses a close-up to hide inconsistent mask handling, preserves the actual comic reply, and uses modest timing adjustment. Both characters remain fully dressed in this episode. Captions follow the retained dialogue. Music ducks for dialogue; original Foley remains, with only quiet mask and comic accents added.

## User-requested photo ending revision
The final five seconds now show the two actual user-supplied production photographs: black armor and mask, followed by the uncovered face. A 0.6-second crossfade connects them; the actor/role credit is enlarged to 44px. No photo regeneration and no additional provider charge. Runtime remains 45 seconds.

Use `python3 render_story.py --masked-photo /path/masked.jpeg --unmasked-photo /path/face.jpeg`, then `python3 finish_photo_ending.py --audio-source /path/previous-finished-video.mp4`. The second command copies the prior mastered audio without re-encoding, preserving dialogue, music, effects and synchronization. The photo revision replaces the previous delivered file.

## First sword handling correction
Run `python3 trim_first_sword.py` after the photo ending revision. This removes source frames 552 through 580 (18.400–19.367 seconds), cutting directly to the existing mask close-up. A centered 80 ms audio crossfade smooths the seam without changing subsequent synchronization. Result: approximately 44.03 seconds. The actual-photo ending, all dialogue and later action remain.

## Arrow entrance correction
Run `python3 trim_action.py` using the 45-second photo master. It applies both approved action trims in one encode: original frames 552–580 and 847–884. The second cut removes about 1.27 seconds of the arrow entrance from the prior version, jumping to the parry. Both audio seams use centered 80 ms crossfades. Result: approximately 42.77 seconds; all spoken dialogue and the five-second photo ending remain.

## iPhone Photos compatibility repair
Final delivery must run `python3 export_iphone.py` after all editorial cuts. An iPhone Photos save failure was reported. Inspection found the prior cut signalled H.264 level 6.2 with a microsecond time base and full-range video. The exporter explicitly uses H.264 Main level 4.0, limited-range 8-bit 4:2:0, constant 30 fps, encoder time base 1/30, MP4 video track time scale 30000, AAC-LC stereo and faststart. It validates these properties and fully decodes the result. This removes the observed encoding compatibility risk; actual saving to the user device must still be confirmed there. The film retains 1283 frames (42.77 seconds), all previous trims and the real-photo ending.
