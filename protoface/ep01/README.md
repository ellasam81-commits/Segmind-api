# 《十三扇门》第1集《被抹除的地址，三声敲门》

**作者 林爱丽 / Written by Lin Aili**

This production uses four nine-panel storyboard sheets, one 15-second clip per
sheet, for exactly one minute. Each sheet's nine clean narrative pictures are
sent separately to MiniMax H3 as nine visual references. Header text, dialogue
boxes and reference tables are excluded from the video inputs.

The source is the user's episode-one script. There is only one speaking
character: **沈照夜, male**. An Ning and female voices are not introduced. The
episode uses one ordinary unnumbered brass key; the engraved13 key belongs to
later episodes. No monster or knocking person is shown at the ending.

## Deliverables

- `raw/segment-01.mp4` through `raw/segment-04.mp4`: four 15-second 16:9 clips
  with native Mandarin dialogue and sound effects, **no added subtitles or BGM**.
- `episode01-clean-dialogue.mp4`: the four clips combined into 60 seconds,
  without added subtitles or BGM.
- `episode01-bilingual-bgm.mp4`: the same minute with Chinese/English subtitles,
  original suspense BGM, series title, episode number and author 林爱丽.
- A separate bilingual SRT, ASS and original BGM WAV.

Music is added only in the final edit and ducks under the native dialogue.
Provider dialogue is preserved rather than replaced with silent stills. The
first generated clip establishes the male voice; its audio is used as a voice
reference for the remaining clips. Exactly six Foley knocks are added in two
groups of three, matching the source script. The generation prompt explicitly
excludes native knocks to prevent double-counting.

Native audiovisual generation is probabilistic: stable-face, exact-wording,
lip-sync and voice-reference instructions are supplied, but must still be
checked in the rendered first cut. Subtitle time ranges are designed cue
points; they are not an automatic transcription or forced alignment of the
resulting speech. Do not describe an unreviewed output as guaranteed exact.

## Start or resume from your phone

The existing GitHub repository secret `PROTOFACE_API_KEY` is used. Never put
the full key into a workflow input, file, comment, or chat.

The initial `request.json` commit starts the episode requested in this chat.
Only changes to that request file trigger generation on push; normal code
changes do not. This means editing the request file can spend credits.

For another deliberate run: **Actions → Thirteen Doors EP01 - four 15s clips →
Run workflow**. Choose the mode and quality, tick **confirm_spend**, then run.
Full-episode mode submits at most four 15-second paid generations. A new run
has new idempotency keys and can charge again. The provider reports the credit
estimate after each acceptance; this workflow is not a price ceiling.

If interrupted, use **Re-run jobs on the same GitHub run**. Its checkpoint
restores run IDs, already-downloaded native clips and the established voice
reference. Failed/canceled runs stop the job without automatic regeneration.
Waiting stops after 25 minutes per clip without canceling the provider's run.

The repository is public. Episode reference frames, workflow logs, generated
artifacts and prompts may be visible to others. The complete60-episode DOCX is
not included; the production manifest contains only episode1.

The retired `protoface/drama/production` draft was for the earlier episode4
discussion. It has no active production workflow. Use this episode1 folder.
