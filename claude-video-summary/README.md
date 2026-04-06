# Claude Video Summary Skill

Claude Code 的视频总结技能，支持本地视频和在线视频（YouTube、Bilibili）的语音转录和 AI 总结。

## 功能特性

- 支持本地 `.mp4` 文件和在线视频 URL
- 自动提取内嵌字幕（Bilibili 需登录）
- Whisper GPU 加速语音转录
- Claude Haiku AI 生成结构化总结
- 长视频（>40分钟）自动分块处理
- 自动清理临时文件

## 安装

### 1. 安装依赖

```bash
pip install faster-whisper
```

### 2. 安装 yt-dlp

```bash
pip install yt-dlp
```

### 3. 安装 ffmpeg

需要将 ffmpeg 添加到系统 PATH，或将 ffmpeg 放在项目目录的 `ffmpeg-8.1-essentials_build/bin` 下。

### 4. 配置 Claude Code Skill

将 `SKILL.md` 复制到 Claude Code 的 skill 目录：

```
.claude/skills/video-summary/SKILL.md
.claude/skills/video-summary/scripts/video_summary.py
```

## 使用方法

### 1. 运行转录脚本

```bash
python .claude/skills/video-summary/scripts/video_summary.py "<视频路径或URL>"
```

脚本会自动：
- 下载视频/提取音频
- 尝试提取字幕（无字幕时使用 Whisper 转录）
- 保存转录结果到 `transcript.txt`
- 保存视频信息到 `video_info.json`
- 清理临时文件

### 2. 生成 AI 总结

在 Claude Code 中继续对话，读取转录结果生成总结。

**普通视频**：直接生成结构化总结

**长视频（>40分钟）**：分块处理，先总结各段再合并

## 输出文件

| 文件 | 说明 |
|------|------|
| `transcript.txt` | 转录文本 |
| `video_info.json` | 视频信息（标题、时长、是否需要分块） |
| `ai总结/*.md` | AI 生成的总结文件 |

## 工作流程

```
用户: /video-summary <URL>
    ↓
Claude Code: 运行转录脚本
    ↓
脚本: 下载音频 → Whisper转录 → 保存结果
    ↓
Claude Code: 读取结果 → 生成AI总结
```

## 环境要求

- Python 3.8+
- NVIDIA GPU（Whisper 转录加速）
- 网络连接（下载在线视频）

## 项目结构

```
claude-video-summary/
├── SKILL.md                    # Skill 定义文档
├── scripts/
│   └── video_summary.py       # 转录脚本
├── README.md
└── LICENSE
```

## License

MIT
