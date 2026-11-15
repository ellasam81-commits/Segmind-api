# 挂播？挂在哪儿？— Protoface chibi mini drama

42 seconds, 6 scenes x 7 seconds, 16:9, 480p, Mandarin dialogue, T Hoo Hoo and anime Tan Jianci.
Author: 林爱丽. This is an independent fan-made skit, not connected to any official ranking platform.

## Phone instructions

1. Open the [new GitHub Actions workflow](https://github.com/ellasam81-commits/Segmind-api/actions/workflows/thoo-hoo-hangbo.yml).
2. Tap Run workflow. Default action=inspect_model: **free**, checks the live model schema and pricing.
3. To generate ONE 7s test, select generate_range, start_scene=1, end_scene=1.
4. To generate all 42s, select generate_range, start_scene=1, end_scene=6.
5. Use the model pricing from the free inspection to enter a positive max_total_credits; zero blocks all paid requests. Tick confirm_spend.
6. Download the run artifact (MP4 clips, subtitles.srt and—if ffmpeg joins successfully—hangbo_42s.mp4). Review spoken audio before publishing.

## Production rules

- The GitHub Secret PROTOFACE_API_KEY is read, never printed or committed.
- The reference asset is a copy of the previous T Hoo Hoo QQ Music storyboard. It is used for character appearance only, NEVER to display a grid.
- No automatic paid runs, scheduled runs, or retries that create replacement requests. Re-run the SAME GitHub run after errors using its saved checkpoint/idempotency key.
- Historical ranking values excluded. Follow the current platform rules; playback is not guaranteed to count toward the chart.
- This project has separate code, prompts, output and concurrency group. It does NOT touch 十三扇门 or the existing QQ Music tutorial.
- The public GitHub repository is publicly viewable. Do not add private photos or credentials to GitHub files.
- No copyrighted song audio is embedded. Add licensed music only when permitted.
- Provider API and credit prices change; the workflow checks the LIVE model schema and price before any paid requests.

## Story
1. Day-chart surprise / 2. Mascot literally hangs a phone / 3. Idol corrects the misunderstanding / 4. QQ Music play tutorial / 5. Music while doing everyday tasks / 6. Hangbo three times and friendly closing.
