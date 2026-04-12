---
name: video-summary
description: Summarize videos from local .mp4 files or online sources (YouTube, Bilibili). Extracts embedded subtitles or uses Whisper AI for transcription, then generates a structured markdown summary. Use when user provides a video path or URL and wants a written summary.
---

# Video Summary Skill

Summarize videos from local files or online sources (YouTube, Bilibili).

## Usage

```
/video-summary <video-path-or-url>
```

## Features

- Local `.mp4` files and online video URLs
- Embedded subtitle extraction or Whisper AI transcription
- Claude Haiku powered summary generation
- Long video chunked processing (>40 min)

## Output

- Transcript: `transcript.txt`
- Video info: `video_info.json`
- AI Summary: `ai总结/{title}.md`
