"""
FFmpeg output parsing and duration helpers
"""
import re
import os
from typing import Any, Dict, Optional


def format_duration(seconds: float) -> str:
    """
    Форматирование длительности в HH:MM:SS.ms.

    Args:
        seconds: Длительность в секундах

    Returns:
        Строка вида HH:MM:SS.xx
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def parse_duration(duration_str: str) -> float:
    """
    Парсинг длительности из строки (HH:MM:SS.xx или секунды).

    Args:
        duration_str: Строка длительности от ffprobe или число секунд

    Returns:
        Длительность в секундах (float)
    """
    if not duration_str:
        return 0.0
    # Попытка как число
    try:
        return float(duration_str)
    except ValueError:
        pass
    # Формат HH:MM:SS.xx или MM:SS.xx
    parts = duration_str.strip().split(":")
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        return 0.0
    try:
        return float(h) * 3600 + float(m) * 60 + float(s)
    except ValueError:
        return 0.0


def parse_ffmpeg_output(stderr: str) -> Dict[str, Any]:
    """
    Извлечение метаданных из stderr вывода FFmpeg/ffprobe.

    Args:
        stderr: Текст stderr

    Returns:
        Словарь с полями (duration, width, height, codec_name и т.д.)
    """
    result: Dict[str, Any] = {}
    # Duration: 00:01:23.45
    m = re.search(r"Duration:\s*(\d{2}:\d{2}:\d{2}\.\d{2})", stderr)
    if m:
        result["duration"] = parse_duration(m.group(1))
    # Video: h264, 1920x1080, 30 fps
    m = re.search(
        r"Video:\s*\w+\s*\(?([^,\)]+)\)?[^,]*,\s*(\d+)x(\d+)",
        stderr,
    )
    if m:
        result["video_codec"] = m.group(1).strip()
        result["width"] = int(m.group(2))
        result["height"] = int(m.group(3))
    m = re.search(r"(\d+(?:\.\d+)?)\s*fps", stderr, re.I)
    if m:
        result["fps"] = float(m.group(1))
    return result


def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """
    Получение метаданных файла (размер, существование).
    Не вызывает FFmpeg — только os.stat.

    Args:
        file_path: Путь к файлу

    Returns:
        Словарь с size, exists и т.д.
    """
    result: Dict[str, Any] = {"exists": os.path.exists(file_path)}
    if result["exists"] and os.path.isfile(file_path):
        try:
            st = os.stat(file_path)
            result["size"] = st.st_size
            result["mtime"] = st.st_mtime
        except OSError:
            result["size"] = 0
    else:
        result["size"] = 0
    return result
