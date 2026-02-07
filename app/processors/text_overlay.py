"""
Text overlay processor: drawtext filter with styling and animations
"""
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from app.ffmpeg.commands import FFmpegCommand
from app.ffmpeg.exceptions import FFmpegValidationError
from app.processors.base_processor import BaseProcessor
from app.utils.temp_files import create_temp_file


class TextOverlay(BaseProcessor):
    """Наложение текста на видео через FFmpeg drawtext фильтр"""

    async def validate_input(self) -> None:
        """Проверка видео файла, текста, временных границ"""
        video_path = self.config.get("video_path")
        if not video_path or not os.path.isfile(video_path):
            raise FFmpegValidationError("Video file not found or inaccessible")

        text = self.config.get("text", "")
        if not text or not text.strip():
            raise FFmpegValidationError("Text cannot be empty")

        # Проверка видео файла на валидность
        try:
            video_info = await FFmpegCommand.get_video_info(video_path)
            if not video_info.get("duration"):
                raise FFmpegValidationError("Video has no duration")
        except Exception as e:
            raise FFmpegValidationError(f"Invalid video file: {str(e)}")

        # Проверка временных границ
        video_duration = video_info.get("duration", 0)
        start_time = self.config.get("start_time", 0)
        end_time = self.config.get("end_time")

        if start_time >= video_duration:
            raise FFmpegValidationError(
                f"start_time ({start_time}) must be less than video duration ({video_duration})"
            )

        if end_time is not None and end_time > video_duration:
            raise FFmpegValidationError(
                f"end_time ({end_time}) cannot exceed video duration ({video_duration})"
            )

        if end_time is not None and end_time <= start_time:
            raise FFmpegValidationError(
                f"end_time ({end_time}) must be greater than start_time ({start_time})"
            )

    async def process(self) -> Dict[str, Any]:
        """Наложение текста с генерацией drawtext фильтра"""
        video_path = self.config.get("video_path")
        output_path = self.config.get("output_path")

        if not output_path:
            output_path = create_temp_file(suffix=".mp4", prefix="text_overlay_")
            self.add_temp_file(output_path)

        # Генерация drawtext фильтра
        filter_chain = self._generate_drawtext_filter()

        # Получаем информацию о видео для прогресса
        video_info = await FFmpegCommand.get_video_info(video_path)
        duration = video_info.get("duration", 0)

        # Генерация команды FFmpeg
        from app.config import get_settings
        settings = get_settings()
        ffmpeg = getattr(settings, "FFMPEG_PATH", "ffmpeg")

        cmd = [
            ffmpeg,
            "-y",
            "-i", video_path,
            "-vf", filter_chain,
            "-c:a", "copy",  # Копируем аудио без изменений
            output_path,
        ]

        def progress_cb(progress: float) -> None:
            if duration and duration > 0 and progress is not None:
                pct = min(100.0, max(0.0, 100.0 * progress / duration))
                self.update_progress(pct)
            elif progress is not None:
                self.update_progress(progress)

        await FFmpegCommand.run_command(
            cmd,
            timeout=self.config.get("timeout", 3600),
            progress_callback=progress_cb,
        )
        self.update_progress(100.0)

        return {"output_path": output_path}

    def _calculate_position(self) -> Dict[str, str]:
        """Вычисление координат (absolute/relative)"""
        position_config = self.config.get("position", {})
        pos_type = position_config.get("type", "relative")

        if pos_type == "absolute":
            x = position_config.get("x", 0)
            y = position_config.get("y", 0)
            return {"x": str(x), "y": str(y)}
        else:
            return self._get_relative_position()

    def _get_relative_position(self) -> Dict[str, str]:
        """Получение относительной позиции (9 позиций с формулами FFmpeg)"""
        position_config = self.config.get("position", {})
        position = position_config.get("position", "center")
        margin_x = position_config.get("margin_x", 10)
        margin_y = position_config.get("margin_y", 10)

        # Формулы FFmpeg для 9 позиций
        positions = {
            "top-left": {"x": f"{margin_x}", "y": f"{margin_y}"},
            "top-center": {"x": f"(w-tw)/2", "y": f"{margin_y}"},
            "top-right": {"x": f"w-tw-{margin_x}", "y": f"{margin_y}"},
            "center-left": {"x": f"{margin_x}", "y": f"(h-th)/2"},
            "center": {"x": f"(w-tw)/2", "y": f"(h-th)/2"},
            "center-right": {"x": f"w-tw-{margin_x}", "y": f"(h-th)/2"},
            "bottom-left": {"x": f"{margin_x}", "y": f"h-th-{margin_y}"},
            "bottom-center": {"x": f"(w-tw)/2", "y": f"h-th-{margin_y}"},
            "bottom-right": {"x": f"w-tw-{margin_x}", "y": f"h-th-{margin_y}"},
        }

        return positions.get(position, positions["center"])

    def _generate_drawtext_filter(self) -> str:
        """Генерация drawtext фильтра"""
        params = self._build_drawtext_params()
        return f"drawtext={params}"

    def _build_drawtext_params(self) -> str:
        """Сборка всех параметров drawtext фильтра"""
        text = self._escape_text(self.config.get("text", ""))
        style = self.config.get("style", {})
        position = self._calculate_position()
        background = self.config.get("background", {})
        border = self.config.get("border", {})
        shadow = self.config.get("shadow", {})
        animation = self.config.get("animation", {})
        rotation = self.config.get("rotation", 0)
        opacity = self.config.get("opacity", 1.0)
        start_time = self.config.get("start_time", 0)
        end_time = self.config.get("end_time")

        params = []

        # Текст
        params.append(f"text='{text}'")

        # Шрифт
        font_family = style.get("font_family", "Arial")
        font_size = style.get("font_size", 24)
        font_weight = style.get("font_weight", "normal")
        params.append(f"fontfile='{self._get_font_path(font_family)}'")
        params.append(f"fontsize={font_size}")

        # Цвет текста
        color = style.get("color", "white")
        alpha = style.get("alpha", 1.0)
        text_color = self._color_to_hex(color, alpha)
        params.append(f"fontcolor={text_color}")

        # Позиция
        params.append(f"x={position['x']}")
        params.append(f"y={position['y']}")

        # Background
        bg_params = self._build_background_params(background)
        if bg_params:
            params.extend(bg_params)

        # Border
        border_params = self._build_border_params(border)
        if border_params:
            params.extend(border_params)

        # Shadow
        shadow_params = self._build_shadow_params(shadow)
        if shadow_params:
            params.extend(shadow_params)

        # Rotation
        if rotation != 0:
            params.append(f"rotation={rotation}")

        # Opacity
        if opacity < 1.0:
            params.append(f"alpha='{opacity}'")

        # Animation
        anim_params = self._build_animation_params(animation, start_time, end_time)
        if anim_params:
            params.extend(anim_params)

        return ":".join(params)

    def _escape_text(self, text: str) -> str:
        """Экранирование спецсимволов для FFmpeg"""
        # FFmpeg drawtext требует экранирования: ' -> \'\\\'\', : -> \:, = -> \=, # -> \#, [ -> \[, ] -> \]
        escaped = text
        escaped = escaped.replace("'", "'\\''")  # Экранирование одинарных кавычек
        escaped = escaped.replace(":", "\\:")
        escaped = escaped.replace("=", "\\=")
        escaped = escaped.replace("#", "\\#")
        escaped = escaped.replace("[", "\\[")
        escaped = escaped.replace("]", "\\]")
        escaped = escaped.replace("{", "\\{")
        escaped = escaped.replace("}", "\\}")
        escaped = escaped.replace("%", "\\%")
        escaped = escaped.replace("\\", "\\\\")
        return escaped

    def _color_to_hex(self, color: str, alpha: float = 1.0) -> str:
        """Конвертация цвета из #RRGGBB в &HRRGGBB& (FFmpeg format)"""
        # Убираем #
        hex_color = color.lstrip("#")
        # Конвертируем в формат FFmpeg: &HBBGGRR& (обратный порядок: blue, green, red)
        r = hex_color[0:2]
        g = hex_color[2:4]
        b = hex_color[4:6]
        # Добавляем alpha канал в начало
        a = int(255 * alpha)
        return f"&H{a:02X}{b}{g}{r}&"

    def _build_background_params(self, background: Dict[str, Any]) -> List[str]:
        """Генерация параметров background"""
        if not background.get("enabled", False):
            return []

        params = []
        color = background.get("color", "black")
        alpha = background.get("alpha", 0.5)
        padding = background.get("padding", 10)
        border_radius = background.get("border_radius", 5)

        bg_color = self._color_to_hex(color, alpha)
        params.append(f"box=1")
        params.append(f"boxcolor={bg_color}")
        params.append(f"boxborderw={padding}")

        # Border radius через boxradius (если доступно в FFmpeg)
        if border_radius > 0:
            params.append(f"boxradius={border_radius}")

        return params

    def _build_border_params(self, border: Dict[str, Any]) -> List[str]:
        """Генерация параметров border"""
        if not border.get("enabled", False):
            return []

        params = []
        width = border.get("width", 2)
        color = border.get("color", "black")

        border_color = self._color_to_hex(color, 1.0)
        params.append(f"borderw={width}")
        params.append(f"bordercolor={border_color}")

        return params

    def _build_shadow_params(self, shadow: Dict[str, Any]) -> List[str]:
        """Генерация параметров shadow"""
        if not shadow.get("enabled", False):
            return []

        params = []
        offset_x = shadow.get("offset_x", 2)
        offset_y = shadow.get("offset_y", 2)
        blur = shadow.get("blur", 2)
        color = shadow.get("color", "black")

        shadow_color = self._color_to_hex(color, 1.0)
        params.append(f"shadowx={offset_x}")
        params.append(f"shadowy={offset_y}")
        params.append(f"shadowcolor={shadow_color}")

        if blur > 0:
            params.append(f"shadoww={blur}")

        return params

    def _build_animation_params(
        self,
        animation: Dict[str, Any],
        start_time: float,
        end_time: Optional[float]
    ) -> List[str]:
        """Генерация параметров анимации (fade, slide, zoom)"""
        anim_type = animation.get("type", "none")
        if anim_type == "none":
            return []

        params = []
        duration = animation.get("duration", 1.0)
        delay = animation.get("delay", 0.0)

        actual_start = start_time + delay
        actual_end = end_time if end_time is not None else actual_start + duration

        if anim_type == "fade_in":
            # Плавное появление
            enable_expr = f"between(t,{actual_start},{actual_end})"
            alpha_expr = f"((t-{actual_start})/{duration})"
            params.append(f"enable='{enable_expr}'")
            params.append(f"alpha='{alpha_expr}'")

        elif anim_type == "fade_out":
            # Плавное исчезновение
            enable_expr = f"between(t,{actual_start},{actual_end})"
            alpha_expr = f"(1-((t-{actual_start})/{duration}))"
            params.append(f"enable='{enable_expr}'")
            params.append(f"alpha='{alpha_expr}'")

        elif anim_type == "fade":
            # Появление и исчезновение (first half fade in, second half fade out)
            mid_time = actual_start + duration / 2
            enable_expr = f"between(t,{actual_start},{actual_end})"
            alpha_expr = f"if(lt(t,{mid_time}),((t-{actual_start})/({duration}/2)),(1-((t-{mid_time})/({duration}/2))))"
            params.append(f"enable='{enable_expr}'")
            params.append(f"alpha='{alpha_expr}'")

        elif anim_type == "slide_left":
            # Слайд слева направо
            enable_expr = f"between(t,{actual_start},{actual_end})"
            x_expr = f"({actual_end}-t)*w/({duration}*2)"
            params.append(f"enable='{enable_expr}'")
            params.append(f"x='{x_expr}'")

        elif anim_type == "slide_right":
            # Слайд справа налево
            enable_expr = f"between(t,{actual_start},{actual_end})"
            x_expr = f"w-({actual_end}-t)*w/({duration}*2)"
            params.append(f"enable='{enable_expr}'")
            params.append(f"x='{x_expr}'")

        elif anim_type == "slide_up":
            # Слайд снизу вверх
            enable_expr = f"between(t,{actual_start},{actual_end})"
            y_expr = f"h-({actual_end}-t)*h/({duration}*2)"
            params.append(f"enable='{enable_expr}'")
            params.append(f"y='{y_expr}'")

        elif anim_type == "slide_down":
            # Слайд сверху вниз
            enable_expr = f"between(t,{actual_start},{actual_end})"
            y_expr = f"({actual_end}-t)*h/({duration}*2)"
            params.append(f"enable='{enable_expr}'")
            params.append(f"y='{y_expr}'")

        elif anim_type == "zoom_in":
            # Увеличение от 0 до 1
            enable_expr = f"between(t,{actual_start},{actual_end})"
            scale_expr = f"((t-{actual_start})/{duration})"
            # FFmpeg не поддерживает scale напрямую в drawtext, используем fontsize
            # Это упрощенная реализация
            params.append(f"enable='{enable_expr}'")

        elif anim_type == "zoom_out":
            # Уменьшение от 1 до 0
            enable_expr = f"between(t,{actual_start},{actual_end})"
            scale_expr = f"(1-((t-{actual_start})/{duration}))"
            # Упрощенная реализация
            params.append(f"enable='{enable_expr}'")

        return params

    def _get_font_path(self, font_family: str) -> str:
        """
        Получение пути к файлу шрифта.
        Возвращает имя шрифта, FFmpeg найдет его в системе.
        """
        # Для Windows/Linux/macOS FFmpeg может найти шрифты по имени
        # Можно добавить логику для поиска шрифтов в системе
        return font_family
