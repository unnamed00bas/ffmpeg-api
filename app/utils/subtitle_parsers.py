"""
Subtitle parsers for SRT, VTT, ASS, SSA formats
"""
import re
from typing import Any, Dict, List


def parse_srt(content: str) -> List[Dict[str, Any]]:
    """
    Парсинг SRT формата.

    Формат:
    1
    00:00:01,000 --> 00:00:04,000
    Hello World

    Возвращает: [{"index": int, "start": float, "end": float, "text": str}, ...]
    """
    subtitles = []

    # Разбиваем на блоки по двойным переносам строк
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        if not block.strip():
            continue

        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        # Первая строка - индекс
        index_line = lines[0].strip()
        if not index_line.isdigit():
            # Если первая строка не число, пробуем следующий формат (без индекса)
            time_line = lines[0].strip()
            text_lines = lines[1:]
            index = None
        else:
            index = int(index_line)
            time_line = lines[1].strip()
            text_lines = lines[2:]

        # Парсим время: 00:00:01,000 --> 00:00:04,000
        time_match = re.match(
            r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2}),(\d{3})",
            time_line,
        )
        if not time_match:
            raise ValueError(f"Invalid time format in SRT block: {time_line}")

        start_time = _parse_srt_time(f"{time_match.group(1)}:{time_match.group(2)}:{time_match.group(3)},{time_match.group(4)}")
        end_time = _parse_srt_time(f"{time_match.group(5)}:{time_match.group(6)}:{time_match.group(7)},{time_match.group(8)}")

        # Текст может быть многострочным
        text = "\n".join(text_lines).strip()

        subtitles.append({
            "index": index,
            "start": start_time,
            "end": end_time,
            "text": text,
        })

    return subtitles


def _parse_srt_time(time_str: str) -> float:
    """
    Парсинг времени SRT (HH:MM:SS,mmm).

    Возвращает время в секундах.
    """
    # Формат: HH:MM:SS,mmm
    match = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", time_str)
    if not match:
        raise ValueError(f"Invalid SRT time format: {time_str}")

    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    milliseconds = int(match.group(4))

    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def parse_vtt(content: str) -> List[Dict[str, Any]]:
    """
    Парсинг WebVTT формата.

    Формат:
    WEBVTT

    00:00:01.000 --> 00:00:04.000
    Hello World

    Возвращает: [{"start": float, "end": float, "text": str}, ...]
    """
    subtitles = []

    lines = content.split("\n")

    # Пропускаем WEBVTT заголовок и пустые строки
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line and not line.startswith("WEBVTT"):
            break
        i += 1

    while i < len(lines):
        line = lines[i].strip()

        # Пропускаем пустые строки и комментарии
        if not line or line.startswith("NOTE") or line.startswith("STYLE"):
            i += 1
            continue

        # Проверяем на временную метку: 00:00:01.000 --> 00:00:04.000
        # Или: 00:00:01.000 --> 00:00:04.000 align:center
        time_match = re.match(
            r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})(?:\s.*)?",
            line,
        )
        if time_match:
            start_time = _parse_vtt_time(
                f"{time_match.group(1)}:{time_match.group(2)}:{time_match.group(3)}.{time_match.group(4)}"
            )
            end_time = _parse_vtt_time(
                f"{time_match.group(5)}:{time_match.group(6)}:{time_match.group(7)}.{time_match.group(8)}"
            )

            # Собираем текст (может быть несколько строк)
            i += 1
            text_lines = []
            while i < len(lines):
                next_line = lines[i].strip()
                if not next_line or re.match(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->", next_line):
                    break
                text_lines.append(next_line)
                i += 1

            text = "\n".join(text_lines).strip()

            subtitles.append({
                "start": start_time,
                "end": end_time,
                "text": text,
            })
        else:
            i += 1

    return subtitles


def _parse_vtt_time(time_str: str) -> float:
    """
    Парсинг времени WebVTT (HH:MM:SS.mmm).

    Возвращает время в секундах.
    """
    # Формат: HH:MM:SS.mmm (использует точки вместо запятых)
    match = re.match(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})", time_str)
    if not match:
        raise ValueError(f"Invalid VTT time format: {time_str}")

    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    milliseconds = int(match.group(4))

    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def parse_ass(content: str) -> List[Dict[str, Any]]:
    """
    Парсинг ASS формата.

    Формат:
    Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello World

    Возвращает: [{"layer": int, "start": float, "end": float, "style": str,
                 "name": str, "margin_l": int, "margin_r": int, "margin_v": int,
                 "effect": str, "text": str}, ...]
    """
    subtitles = []

    lines = content.split("\n")

    for line in lines:
        line = line.strip()

        # Парсим только строки Dialogue
        if not line.startswith("Dialogue:"):
            continue

        # Убираем префикс Dialogue:
        line = line[9:].strip()

        # Поля разделены запятыми, но поле Text может содержать запятые
        # Формат: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        parts = line.split(",", 9)

        if len(parts) < 10:
            # Если меньше 10 частей, пробуем считать текст как последнее поле
            # (без эффекта)
            if len(parts) >= 9:
                parts.append("")
            else:
                continue

        try:
            layer = int(parts[0].strip())
            start_time = _parse_ass_time(parts[1].strip())
            end_time = _parse_ass_time(parts[2].strip())
            style = parts[3].strip()
            name = parts[4].strip()
            margin_l = int(parts[5].strip())
            margin_r = int(parts[6].strip())
            margin_v = int(parts[7].strip())
            effect = parts[8].strip()
            text = parts[9].strip()

            # Обработка ASS тегов в тексте (например, {\b1}, {\i1}, {\c&H00FFFFFF&})
            # Пока оставляем текст как есть - FFmpeg обработает теги
        except (ValueError, IndexError):
            continue

        subtitles.append({
            "layer": layer,
            "start": start_time,
            "end": end_time,
            "style": style,
            "name": name,
            "margin_l": margin_l,
            "margin_r": margin_r,
            "margin_v": margin_v,
            "effect": effect,
            "text": text,
        })

    return subtitles


def _parse_ass_time(time_str: str) -> float:
    """
    Парсинг времени ASS (H:MM:SS.mm).

    Возвращает время в секундах.
    """
    # Формат: H:MM:SS.mm (час может быть одной или двумя цифрами)
    match = re.match(r"(\d{1,2}):(\d{2}):(\d{2})\.(\d{2})", time_str)
    if not match:
        raise ValueError(f"Invalid ASS time format: {time_str}")

    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    centiseconds = int(match.group(4))

    return hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0


def parse_ssa(content: str) -> List[Dict[str, Any]]:
    """
    Парсинг SSA формата (использует ту же логику, что и ASS).

    SSA является предшественником ASS и имеет похожий формат.
    """
    return parse_ass(content)
