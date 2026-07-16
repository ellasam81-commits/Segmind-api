# 《愈合之前》EP01 第一段：Segmind 生成流程

这套流程把一张 12 格分镜拆成 **3 个 5 秒片段**，用 Segmind `seedance-2.0-mini` 生成后再合并成 15 秒视频。

它不是把整张十二宫格直接丢给模型。每段只引用 4 张对应画格，并把镜头顺序、动作、角色和时间写死，因此更接近原分镜，也较不容易出现乱演、人物突变或漫画格线被拍进视频。

## 已固定的声音

- 解说：沉稳男声
- 林浅：冷静年轻女声
- 陆沉：克制低沉男声

脚本会先生成固定中文语音，再把语音交给 Seedance 做口型参考，最后把原语音重新混回成片。即使 Seedance 某段没生成声音，最终文件仍有完整解说和对白；脚本还会检查音轨，没有声音就直接报错，不会把无声文件当成成品。

## iPhone 第一次设置

1. 打开本仓库，进入 **Settings**。
2. 进入 **Secrets and variables** → **Actions**。
3. 点 **New repository secret**。
4. Name 填 `SEGMIND_API_KEY`，Secret 填你的 Segmind API Key，然后保存。

API Key 只放在 GitHub Secret，绝不能贴进代码、README 或聊天截图。

## iPhone 一键生成

1. 打开仓库上方的 **Actions**。
2. 点左边 **Generate EP01 Part01 with Segmind**。
3. 点 **Run workflow**。
4. 第一次选 `480p`；Seed 填 `1701`；把 `confirm_spend` 改成 `YES`。
5. 完成后打开该次运行，在最下面下载 `ep01-part01-480p-seed-1701`。
6. ZIP 内的 `ep01_part01_final.mp4` 是 15 秒成片，`ep01_part01.srt` 是准确字幕文件。

建议先看 480p。画面和动作确认无误后才跑 720p，避免浪费 credits。每次按 Run 都会产生新的 Segmind 费用；工作流不会自动重试。

## 本地验证（不花 Segmind credits）

```bash
python src/generate_episode.py \
  --config episode/ep01_part01.json \
  --storyboard assets/ep01_part01_storyboard.jpg \
  --dry-run --skip-tts
```

当前镜头与对白都在 `episode/ep01_part01.json`，修改剧情时只需要改这一份文件。

