"""
Subtitle processor: overlay subtitles on video
"""
import os
from typing import Any, Dict, List, Optional

from app.ffmpeg.commands import FFmpegCommand
from app.ffmpeg.exceptions import FFmpegValidationError
from app.processors.base_processor import BaseProcessor
from app.schemas.subtitle import SubtitleFormat, SubtitlePosition, SubtitleStyle
from app.utils.subtitle_parsers import (
    parse_ass,
    parse_srt,
    parse_ssa,
    parse_vtt,
)
from app.utils.temp_files import create_temp_file, create_temp_dir


class SubtitleProcessor(BaseProcessor):
    """Процессор наложения субтитров на видео."""

    async def validate_input(self) -> None:
        """
        Валидация входных данных:
        - Проверка видео файла
        - Проверка субтитров файла (если есть)
        - Проверка текста субтитров (если есть)
        - Проверка формата
        """
        video_path = self.config.get("video_path")
        if not video_path or not os.path.isfile(video_path):
            raise FFmpegValidationError("Video file not found")

        # Проверяем, что это видео файл
        try:
            info = await FFmpegCommand.get_video_info(video_path)
            if not info.get("has_video"):
                raise FFmpegValidationError("Input file is not a video")
        except Exception as e:
            raise FFmpegValidationError(f"Failed to read video info: {e}")

        # Проверяем, что указан хотя бы один источник субтитров
        subtitle_file_path = self.config.get("subtitle_file_path")
        subtitle_text = self.config.get("subtitle_text")

        if subtitle_file_path:
            if not os.path.isfile(subtitle_file_path):
                raise FFmpegValidationError("Subtitle file not found")

            # Проверяем, что указан формат
            subtitle_format = self.config.get("format")
            if not subtitle_format:
                raise FFmpegValidationError("Subtitle format not specified")
        elif subtitle_text:
            if not isinstance(subtitle_text, list) or len(subtitle_text) == 0:
                raise FFmpegValidationError("Subtitle text must be a non-empty list")

            # Проверяем формат каждого субтитра
            for i, entry in enumerate(subtitle_text):
                if not isinstance(entry, dict):
                    raise FFmpegValidationError(f"Subtitle entry {i} must be a dict")
                if "start" not in entry or "end" not in entry or "text" not in entry:
                    raise FFmpegValidationError(
                        f"Subtitle entry {i} must have start, end, and text fields"
                    )
                if entry["start"] >= entry["end"]:
                    raise FFmpegValidationError(
                        f"Subtitle entry {i}: start time must be less than end time"
                    )
        else:
            raise FFmpegValidationError(
                "Either subtitle_file_path or subtitle_text must be provided"
            )

    async def _parse_subtitle_file(
        self, file_path: str, subtitle_format: SubtitleFormat
    ) -> List[Dict[str, Any]]:
        """
        Парсинг файла субтитров.

        Вызывает соответствующий парсер в зависимости от формата.
        """
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if subtitle_format == SubtitleFormat.SRT:
            return parse_srt(content)
        elif subtitle_format == SubtitleFormat.VTT:
            return parse_vtt(content)
        elif subtitle_format == SubtitleFormat.ASS:
            return parse_ass(content)
        elif subtitle_format == SubtitleFormat.SSA:
            return parse_ssa(content)
        else:
            raise FFmpegValidationError(f"Unsupported subtitle format: {subtitle_format}")

    def _generate_subtitle_from_text(self, subtitle_text: List[Dict[str, Any]]) -> str:
        """
        Генерация файла субтитров из текста (в формате SRT).

        Временные интервалы распределяются равномерно.
        """
        lines = []
        for idx, entry in enumerate(subtitle_text, 1):
            start = entry["start"]
            end = entry["end"]
            text = entry["text"]

            # Форматируем время в SRT: HH:MM:SS,mmm
            start_time = self._format_srt_time(start)
            end_time = self._format_srt_time(end)

            lines.append(str(idx))
            lines.append(f"{start_time} --> {end_time}")
            lines.append(text)
            lines.append("")  # Пустая строка между записями

        return "\n".join(lines)

    def _format_srt_time(self, seconds: float) -> str:
        """Форматирование времени в SRT формат (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"

    def _generate_ass_style(self, style: SubtitleStyle) -> str:
        """
        Генерация ASS стилей в формате FFmpeg.

        Формат:
        Style: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,
               BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,
               Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
        """
        # ASS использует формат &HAABBGGRR, но мы уже передаем в этом формате
        # Дополнительные биты для back_color (прозрачность уже включена)

        return (
            f"Style: Default,{style.font_name},{style.font_size},"
            f"{style.primary_color},{style.secondary_color},"
            f"{style.outline_color},{style.back_color},"
            f"{1 if style.bold else 0},"
            f"{1 if style.italic else 0},"
            f"{1 if style.underline else 0},"
            f"{1 if style.strikeout else 0},"
            f"{style.scale_x:.1f},{style.scale_y:.1f},"
            f"{style.spacing:.1f},{style.angle:.1f},"
            f"{style.border_style},"
            f"{style.outline:.1f},{style.shadow:.1f},"
            f"{style.alignment},"
            f"{style.margin_l},{style.margin_r},{style.margin_v},"
            f"{style.encoding}"
        )

    def _generate_ffmpeg_command(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        subtitle_format: SubtitleFormat,
        style: Optional[SubtitleStyle] = None,
        position: Optional[SubtitlePosition] = None,
    ) -> List[str]:
        """
        Генерация FFmpeg команды для наложения субтитров.

        Для ASS/SSA: subtitles фильтр с поддержкой стилей.
        Для SRT/VTT: subtitles фильтр с конвертацией.
        """
        from app.config import get_settings

        settings = get_settings()
        ffmpeg = getattr(settings, "FFMPEG_PATH", "ffmpeg")

        cmd = [ffmpeg, "-y", "-i", video_path]

        if subtitle_format in (SubtitleFormat.ASS, SubtitleFormat.SSA):
            # Для ASS/SSA используем subtitles фильтр напрямую
            # ASS формат поддерживает стили и позиционирование
            filter_complex = f"subtitles='{subtitle_path}'"

            # Добавляем опции фильтра если нужно
            filter_opts = []
            if style:
                # FFmpeg subtitles фильтр не поддерживает изменение стилей ASS напрямую
                # Стили берутся из ASS файла
                pass

            if position and position.position:
                # Позиционирование для ASS сложнее, так как оно определяется в самом файле
                # Для простого позиционирования можно использовать force_style
                if position.position == "top":
                    filter_opts.append("Alignment=6")  # Top-center
                elif position.position == "center":
                    filter_opts.append("Alignment=5")  # Center-center
                elif position.position == "bottom":
                    filter_opts.append("Alignment=2")  # Bottom-center (default)

            if filter_opts:
                filter_complex += f":{','.join(filter_opts)}"

            cmd.extend(["-vf", filter_complex])

        else:
            # Для SRT/VTT также используем subtitles фильтр
            filter_complex = f"subtitles='{subtitle_path}'"

            filter_opts = []
            if position and position.position:
                # Для SRT/VTT можем задавать позицию
                if position.position == "top":
                    filter_opts.append("force_style='Alignment=6'")
                elif position.position == "center":
                    filter_opts.append("force_style='Alignment=5'")
                elif position.position == "bottom":
                    filter_opts.append("force_style='Alignment=2'")

            if style:
                # Применяем стили для SRT/VTT через force_style
                style_parts = []
                if style.font_name:
                    style_parts.append(f"Fontname={style.font_name}")
                if style.font_size:
                    style_parts.append(f"Fontsize={style.font_size}")
                if style.bold:
                    style_parts.append("Bold=1")
                if style.italic:
                    style_parts.append("Italic=1")
                if style.primary_color:
                    style_parts.append(f"PrimaryColour={style.primary_color}")
                if style.outline_color:
                    style_parts.append(f"OutlineColour={style.outline_color}")
                if style.outline:
                    style_parts.append(f"Outline={style.outline:.1f}")
                if style.shadow:
                    style_parts.append(f"Shadow={style.shadow:.1f}")
                if style.alignment:
                    style_parts.append(f"Alignment={style.alignment}")

                if style_parts:
                    style_str = ",".join(style_parts)
                    filter_opts.append(f"force_style='{style_str}'")

            if filter_opts:
                filter_complex += f":{','.join(filter_opts)}"

            cmd.extend(["-vf", filter_complex])

        # Копируем аудио без изменения
        cmd.extend(["-c:a", "copy"])

        # Добавляем выходной файл
        cmd.append(output_path)

        return cmd

    async def process(self) -> Dict[str, Any]:
        """
        Основной процесс наложения субтитров.

        1. Получаем путь к видео и субтитрам
        2. Генерируем файл субтитров (если текст)
        3. Создаем FFmpeg команду
        4. Запускаем обработку
        5. Возвращаем путь к выходному файлу
        """
        video_path = self.config.get("video_path")
        subtitle_file_path = self.config.get("subtitle_file_path")
        subtitle_text = self.config.get("subtitle_text")
        subtitle_format = self.config.get("format", SubtitleFormat.SRT)
        style = self.config.get("style")
        position = self.config.get("position")
        output_path = self.config.get("output_path")

        # Если выходной путь не указан, создаем временный файл
        if not output_path:
            output_path = create_temp_file(suffix=".mp4", prefix="subtitled_")
            self.add_temp_file(output_path)

        # Если текст субтитров задан, генерируем временный файл
        temp_subtitle_path = None
        if subtitle_text:
            if subtitle_format == SubtitleFormat.SRT:
                srt_content = self._generate_subtitle_from_text(subtitle_text)
            else:
                # Для других форматов генерируем SRT, FFmpeg конвертирует
                srt_content = self._generate_subtitle_from_text(subtitle_text)

            temp_subtitle_path = create_temp_file(suffix=".srt", prefix="subtitle_")
            self.add_temp_file(temp_subtitle_path)

            with open(temp_subtitle_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

            subtitle_file_to_use = temp_subtitle_path
        else:
            subtitle_file_to_use = subtitle_file_path

        self.update_progress(10.0)

        # Для ASS формата можем добавить стили в начало файла
        if subtitle_format in (SubtitleFormat.ASS, SubtitleFormat.SSA) and style:
            # Читаем существующий ASS файл
            if os.path.isfile(subtitle_file_to_use):
                with open(subtitle_file_to_use, "r", encoding="utf-8", errors="ignore") as f:
                    ass_content = f.read()

                # Проверяем, есть ли секция Styles
                if "[V4+ Styles]" in ass_content:
                    # Заменяем или добавляем стиль Default
                    new_style = self._generate_ass_style(style)
                    # Простая замена - ищем существующий стиль Default
                    import re

                    style_pattern = r"Style: Default,[^\n]*"
                    if re.search(style_pattern, ass_content):
                        ass_content = re.sub(style_pattern, new_style, ass_content)
                    else:
                        # Добавляем стиль после заголовка секции
                        ass_content = re.sub(
                            r"\[V4\+ Styles\]\n",
                            f"[V4+ Styles]\\n{new_style}\\n",
                            ass_content,
                        )

                    # Перезаписываем файл
                    modified_subtitle_path = create_temp_file(
                        suffix=".ass", prefix="styled_"
                    )
                    self.add_temp_file(modified_subtitle_path)
                    with open(modified_subtitle_path, "w", encoding="utf-8") as f:
                        f.write(ass_content)

                    subtitle_file_to_use = modified_subtitle_path

        self.update_progress(30.0)

        # Генерируем FFmpeg команду
        cmd = self._generate_ffmpeg_command(
            video_path=video_path,
            subtitle_path=subtitle_file_to_use,
            output_path=output_path,
            subtitle_format=subtitle_format,
            style=style,
            position=position,
        )

        # Запускаем FFmpeg
        def progress_cb(progress: float) -> None:
            # Прогресс от 30% до 95%
            if progress is not None:
                scaled = 30.0 + (progress / 100.0) * 65.0
                self.update_progress(scaled)

        await FFmpegCommand.run_command(
            cmd,
            timeout=self.config.get("timeout", 3600),
            progress_callback=progress_cb,
        )

        self.update_progress(100.0)

        return {"output_path": output_path}
