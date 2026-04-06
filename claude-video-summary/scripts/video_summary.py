#!/usr/bin/env python3
"""视频总结脚本 - 支持本地视频和在线视频（YouTube、Bilibili）

此脚本负责：
1. 输入处理（视频下载/音频提取）
2. 语音转录（Whisper GPU 加速）
3. 长视频检测（>40分钟标记为需分块处理）

转录完成后结果保存在 transcript.txt，由 Claude Code 直接读取生成总结。
长视频（>40分钟）会自动标记，Claude Code 会进行分块总结。
"""

import os
import sys
import json
import subprocess
import re
import time
from pathlib import Path
from typing import Optional

# 路径配置
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
FFMPEG_BIN = str(PROJECT_DIR / "ffmpeg-8.1-essentials_build" / "bin")
OUTPUT_DIR = PROJECT_DIR / "ai总结"
TEMP_DIR = PROJECT_DIR / "temp_video_summary"
TRANSCRIPT_FILE = PROJECT_DIR / "transcript.txt"
VIDEO_INFO_FILE = PROJECT_DIR / "video_info.json"

# 长视频阈值（分钟）
LONG_VIDEO_THRESHOLD_MINUTES = 40


def setup_environment():
    """配置环境变量"""
    if FFMPEG_BIN not in os.environ.get("PATH", ""):
        os.environ["PATH"] = FFMPEG_BIN + os.pathsep + os.environ.get("PATH", "")


def is_url(path_or_url: str) -> bool:
    """判断是否为在线URL"""
    return path_or_url.startswith("http://") or path_or_url.startswith("https://")


def run_cmd(cmd, capture=True):
    """执行命令"""
    print(f"[CMD] {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    if capture:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    else:
        subprocess.run(cmd, shell=True)
        return 0, "", ""


def get_video_duration_from_ffprobe(path: Path) -> float:
    """使用 ffprobe 获取视频时长（秒）"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'json',
        str(path)
    ]
    _, stdout, _ = run_cmd(cmd, capture=True)
    try:
        info = json.loads(stdout)
        return float(info.get('format', {}).get('duration', 0))
    except:
        return 0


def get_video_info(url: str) -> tuple:
    """获取视频信息，返回 (标题, 时长(秒), 时长字符串, 来源)"""
    _, stdout, _ = run_cmd(
        f'python -m yt_dlp --dump-json --no-playlist "{url}"',
        capture=True
    )
    title = "video"
    duration_sec = 0
    duration_str = "未知"
    source = "在线视频"

    try:
        info = json.loads(stdout)
        title = info.get("title", "video")
        # 清理标题中的非法字符
        title = re.sub(r'[<>:"/\\|?*]', '_', title)
        duration_sec = info.get("duration", 0)
        minutes = int(duration_sec // 60)
        seconds = int(duration_sec % 60)
        duration_str = f"{minutes}分{seconds}秒"

        if "bilibili.com" in url:
            source = "Bilibili"
        elif "youtube.com" in url:
            source = "YouTube"
        else:
            source = "在线视频"
    except:
        pass

    return title, duration_sec, duration_str, source


def get_local_video_duration(video_path: str) -> float:
    """获取本地视频时长"""
    setup_environment()
    path = Path(video_path)
    if path.suffix.lower() in ['.mp4', '.mkv', '.avi', '.mov', '.flv']:
        return get_video_duration_from_ffprobe(path)
    return 0


def extract_subtitles(url: str) -> Optional[str]:
    """提取字幕文件，返回字幕文本内容"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    original_cwd = os.getcwd()
    os.chdir(TEMP_DIR)

    code, _, _ = run_cmd(
        f'python -m yt_dlp --write-subs --write-auto-subs --sub-lang zh-Hans,zh-Hant,en --skip-download --no-playlist -o "subtitle" "{url}"',
        capture=True
    )

    text_content = None
    if code == 0:
        sub_files = list(TEMP_DIR.glob("*.vtt")) + list(TEMP_DIR.glob("*.srt")) + list(TEMP_DIR.glob("*.ass"))
        if sub_files:
            text_content = subtitles_to_text(sub_files)
            print(f"[INFO] 已提取字幕，共 {len(text_content)} 字符")

    os.chdir(original_cwd)
    return text_content


def subtitles_to_text(sub_files: list) -> str:
    """将字幕文件转换为纯文本"""
    text = ""
    for sub_file in sub_files:
        with open(sub_file, encoding="utf-8") as f:
            content = f.read()
        # 移除 VTT/SRT 标签
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'^\d+$', '', content, flags=re.MULTILINE)
        content = re.sub(r'^\d{2}:\d{2}:\d{2}.*$', '', content, flags=re.MULTILINE)
        text += content + " "
    return text.strip()


def download_audio(url: str) -> Path:
    """下载音频"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = TEMP_DIR / "audio.m4a"

    run_cmd(
        f'python -m yt_dlp -f "bestaudio[ext=m4a]" --no-playlist -o "{audio_path}" "{url}"',
        capture=False
    )
    return audio_path


def extract_audio_local(video_path: str) -> Path:
    """从本地视频提取音频"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = TEMP_DIR / "audio.m4a"

    setup_environment()
    run_cmd(
        f'ffmpeg -i "{video_path}" -vn -acodec copy -y "{audio_path}"',
        capture=False
    )
    return audio_path


def transcribe_whisper(audio_path: Path) -> str:
    """使用 faster-whisper 转录"""
    setup_environment()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[INFO] 正在安装 faster-whisper...")
        subprocess.run([sys.executable, "-m", "pip", "install", "faster-whisper"], check=True)
        from faster_whisper import WhisperModel

    print("[INFO] 正在加载 Whisper 模型 (GPU)...")
    model = WhisperModel("base", device="cuda", compute_type="float16")

    print("[INFO] 正在转录音频...")
    start = time.time()
    segments, info = model.transcribe(str(audio_path), language="zh")
    text = ""
    for segment in segments:
        text += segment.text
    print(f"[INFO] 转录完成，耗时 {time.time() - start:.2f}s，共 {len(text)} 字符")

    return text


def is_long_video(duration_sec: float) -> bool:
    """判断是否为长视频"""
    if duration_sec <= 0:
        return False
    return duration_sec > LONG_VIDEO_THRESHOLD_MINUTES * 60


def save_transcript(title: str, duration_sec: float, duration_str: str, source: str, transcript: str):
    """保存转录结果和视频信息"""
    # 保存转录文本
    with open(TRANSCRIPT_FILE, "w", encoding="utf-8") as f:
        f.write(transcript)
    print(f"[INFO] 转录文本已保存到: {TRANSCRIPT_FILE}")

    # 判断是否长视频
    need_chunk = is_long_video(duration_sec)

    # 保存视频信息
    info = {
        "title": title,
        "duration_seconds": duration_sec,
        "duration": duration_str,
        "source": source,
        "transcript_length": len(transcript),
        "need_chunked_processing": need_chunk,
        "long_video_threshold_minutes": LONG_VIDEO_THRESHOLD_MINUTES
    }
    with open(VIDEO_INFO_FILE, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(f"[INFO] 视频信息已保存到: {VIDEO_INFO_FILE}")

    if need_chunk:
        print(f"[INFO] 检测到长视频（>{LONG_VIDEO_THRESHOLD_MINUTES}分钟），Claude Code 将进行分块总结")


def cleanup():
    """清理临时文件"""
    if TEMP_DIR.exists():
        import shutil
        shutil.rmtree(TEMP_DIR)
        print("[INFO] 临时文件已清理")


def main():
    if len(sys.argv) < 2:
        print("用法: python video_summary.py <视频路径或URL>")
        sys.exit(1)

    video_input = sys.argv[1]
    source = "本地"
    title = "video"
    duration_sec = 0
    duration_str = "未知"
    transcript = ""

    try:
        if is_url(video_input):
            print(f"[INFO] 检测到在线视频: {video_input}")

            # 获取视频信息
            title, duration_sec, duration_str, source = get_video_info(video_input)
            print(f"[INFO] 视频标题: {title}")
            print(f"[INFO] 视频时长: {duration_str}")
            print(f"[INFO] 视频来源: {source}")

            # 尝试提取字幕
            transcript = extract_subtitles(video_input)

            if not transcript:
                print("[INFO] 未找到字幕，下载音频进行转录...")
                audio_path = download_audio(video_input)
                transcript = transcribe_whisper(audio_path)
        else:
            print(f"[INFO] 检测到本地视频: {video_input}")
            title = Path(video_input).stem
            source = "本地"

            # 获取本地视频时长
            duration_sec = get_local_video_duration(video_input)
            if duration_sec > 0:
                duration_str = f"{int(duration_sec // 60)}分{int(duration_sec % 60)}秒"
            print(f"[INFO] 视频时长: {duration_str}")

            audio_path = extract_audio_local(video_input)
            transcript = transcribe_whisper(audio_path)

        # 保存转录结果
        save_transcript(title, duration_sec, duration_str, source, transcript)

        print("\n" + "="*60)
        print("转录完成！")
        if is_long_video(duration_sec):
            print(f"长视频检测（>{LONG_VIDEO_THRESHOLD_MINUTES}分钟），请在 Claude Code 中说：")
            print(f"  '请对这个转录进行分块总结'")
        else:
            print("现在请在 Claude Code 中输入总结指令")
        print("="*60)

    except Exception as e:
        print(f"[ERROR] 处理失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        cleanup()


if __name__ == "__main__":
    main()
