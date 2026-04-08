# video_summary.py 更新文档

版本: 1.2.0
日期: 2026-04-08

---

## 1. 命令执行层重构

### 1.1 run_cmd() 函数签名变更

**旧版:**
```python
def run_cmd(cmd, capture=True):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr
```

**新版:**
```python
class CmdResult(NamedTuple):
    """命令执行结果"""
    returncode: int
    stdout: str
    stderr: str

def run_cmd(cmd, capture=True, shell=False, quiet=False) -> CmdResult:
```

**改进:**
- 新增 `CmdResult` 命名元组，统一返回类型
- 新增 `shell` 参数（默认 False），自动选择模式
- 新增 `quiet` 参数，静默模式
- 字符串命令自动用 `shlex.split()` 转换为列表

### 1.2 调用方式变更

| 函数 | 旧版 | 新版 |
|------|------|------|
| `get_video_duration_from_ffprobe()` | `run_cmd(cmd, capture=True)` | `run_cmd(cmd, capture=True, shell=False)` |
| `get_video_info()` | 字符串命令 | 列表 + `shell=False` |
| `download_audio()` | 字符串命令 | 列表 + `shell=False` |
| `extract_audio_local()` | 字符串命令 | 列表 + `shell=False` |
| `extract_subtitles()` | 字符串命令 | 列表 + `shell=False` |

---

## 2. download_audio() 增强

**改进:**
- 返回 `CmdResult`，检查 returncode
- 添加文件有效性验证
- 失败时抛出明确错误信息

```python
result = run_cmd(cmd, capture=True, shell=False)
if result.returncode != 0:
    raise RuntimeError(f"音频下载失败，返回码: {result.returncode}\nstderr: {result.stderr[:500]}")
if not audio_path.exists() or audio_path.stat().st_size == 0:
    raise RuntimeError("音频下载命令执行后未找到有效音频文件。")
```

---

## 3. extract_audio_local() 智能回退

**改进:**
- 优先尝试 `copy` 模式（无损）
- 失败时自动回退到 AAC 转码
- 日志明确显示使用的模式

```python
# 优先 copy
result = run_cmd(cmd_copy, ...)
if result.returncode == 0 and audio_path.exists():
    return audio_path

# 回退 AAC
result = run_cmd(cmd_aac, ...)
```

日志输出:
- `[INFO] 音频提取完成（copy模式）: ...`
- `[WARN] audio copy 失败，回退到 AAC 转码模式`
- `[INFO] 音频提取完成（AAC模式）: ...`

---

## 4. transcribe_whisper() 设备自动检测

**改进:**
- 自动检测 CUDA 可用性
- 失败时自动回退到 CPU/int8
- 日志明确显示实际使用的设备

```python
# 自动检测设备
device = "cuda"
compute_type = "float16"
try:
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA 不可用")
    test_tensor = torch.zeros(1).cuda()
except Exception as e:
    device = "cpu"
    compute_type = "int8"
```

日志输出:
- `[INFO] 正在检测可用设备...`
- `[INFO] CUDA 检测通过`
- `[INFO] CUDA 不可用，回退到 CPU: ...`
- `[INFO] Whisper 模型加载成功，设备: CUDA / float16`

---

## 5. extract_subtitles() 列表化

**改进:**
- 命令改为列表形式
- `load_cookies()` 返回 `Path` 而非字符串
- cookies 作为独立参数传递

```python
def load_cookies() -> Optional[Path]:
    # 返回 Path 对象，而非字符串
    return cookie_path if cookie_path.exists() else None

# 使用
if cookie_path:
    cmd.extend(['--cookies', str(cookie_path)])
```

---

## 6. generate_summary() 整合

**改进:**
- 整合到主脚本，自动调用
- 新增 `_extract_summary_text()` 辅助函数
- 新增 `_strip_markdown_code_fence()` 辅助函数
- 兼容 Haiku 的 ThinkingBlock 返回格式

```python
def generate_summary():
    # 读取 transcript.txt 和 video_info.json
    # 调用 Claude Haiku 生成总结
    # 保存到 ai总结/{标题}.md

def _extract_summary_text(content_blocks) -> str:
    """从 Claude 返回的 content blocks 中提取文本，跳过 ThinkingBlock"""

def _strip_markdown_code_fence(text: str) -> str:
    """移除包裹摘要的 markdown code fence"""
```

---

## 7. 错误处理增强

**改进:**
- 所有外部命令调用检查 returncode
- 失败时抛出带有 stderr 信息的 RuntimeError
- 文件验证确保输出有效性

```python
if result.returncode != 0:
    raise RuntimeError(
        f"操作失败，返回码: {result.returncode}\n"
        f"stderr: {result.stderr[:500]}"
    )
```

---

## 8. 路径处理改进

**改进:**
- 统一使用 `Path.resolve()` 获取绝对路径
- 避免路径中的空格和特殊字符问题
- 跨平台兼容性提升

```python
video_path_resolved = str(Path(video_path).resolve())
audio_path_resolved = str(audio_path.resolve())
```

---

## 9. 日志输出标准化

**格式:**
```
[INFO] 操作描述
[WARN] 警告信息
[CMD] 命令内容
[ERROR] 错误信息
```

**示例:**
```
[INFO] 检测到在线视频: https://...
[INFO] 视频标题: xxx
[INFO] 视频时长: 10分钟
[CMD] python.exe -m yt_dlp --dump-json ...
[INFO] 未找到字幕，下载音频进行转录...
[INFO] 正在检测可用设备...
[INFO] CUDA 检测通过
[INFO] Whisper 模型加载成功，设备: CUDA / float16
[INFO] 转录完成，耗时 22.5s，共 2269 字符
[INFO] 总结已保存到: ai总结/xxx.md
```

---

## 10. 文件清理行为

**改进:**
- `cleanup()` 移除了 transcript.txt 和 video_info.json 的清理
- 仅清理 temp_video_summary 目录
- 保留转录结果供后续使用

```python
def cleanup():
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)
```

---

## 总结

本次更新主要解决了以下问题:

1. **安全性**: 减少 `shell=True` 依赖，降低命令注入风险
2. **可靠性**: 所有命令添加返回码检查和文件验证
3. **兼容性**: 自动设备检测，本地音频智能回退
4. **可维护性**: 统一返回类型，标准化日志输出
5. **用户体验**: 全流程自动化，无需手动干预
