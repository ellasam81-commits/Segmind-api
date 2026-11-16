# 大哥，我不是氛围灯！

60秒竖屏动漫小剧场：黑衣银色流苏男主与会变色的 T Hoo Hoo 洋娃娃。

- GitHub Actions + Protoface MiniMax H3，五段各12秒，原生480p；全部成功，实际扣费75积分。
- 导出720×1280、24fps、H.264/AAC、faststart，中文对白及字幕。
- 配乐是本项目原创节奏伴奏，不是《Trouble In My DMs》的商业录音；片尾是歌曲推荐。
- 统一参考图保存在 reference.jpg；成片已另行交付，未把大体积视频提交到代码库。
- 保留原生角色配音，通过局部听写校正对白时间，删除重复台词及多余生成声音。
- 未添加制作人署名；画面包含 AI 动漫二创标识。

生成记录：Actions 43874339484，artifact 14229427207。

修改 request.json 会触发本分支生成工作流并可能产生费用。不得为了取回已完成视频重发请求；应下载现有 artifact 或查询已保存的 provider run ID。

postprocess.py 为本地音频清理、字幕、原创音乐和剪辑源代码。音频窗口与字幕时点见 output/ 中的 JSON。源视频需从生成记录下载后放入 output/。
