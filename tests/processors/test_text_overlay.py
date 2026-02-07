"""
Comprehensive tests for text overlay processor
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio

from app.schemas.text_overlay import (
    TextPositionType,
    TextPosition,
    TextStyle,
    TextBackground,
    TextBorder,
    TextShadow,
    TextAnimationType,
    TextAnimation,
    TextOverlayRequest,
)
from app.processors.text_overlay import TextOverlay
from app.ffmpeg.exceptions import FFmpegValidationError


class TestTextOverlaySchemas:
    """Unit тесты для text overlay schemas"""

    def test_text_overlay_request_valid(self):
        """Текстовая запрос валидируется корректно"""
        request = TextOverlayRequest(
            video_file_id=1,
            text="Sample text",
        )
        assert request.video_file_id == 1
        assert request.text == "Sample text"
        assert request.position.type == TextPositionType.RELATIVE
        assert request.style.font_family == "Arial"
        assert request.style.font_size == 24
        assert request.background.enabled is False
        assert request.border.enabled is False
        assert request.shadow.enabled is False
        assert request.animation.type == TextAnimationType.NONE

    def test_text_position_absolute(self):
        """TextPosition работает в absolute режиме"""
        position = TextPosition(
            type=TextPositionType.ABSOLUTE,
            x=100,
            y=200,
        )
        assert position.type == TextPositionType.ABSOLUTE
        assert position.x == 100
        assert position.y == 200

    def test_text_position_relative(self):
        """TextPosition работает в relative режиме"""
        position = TextPosition(
            type=TextPositionType.RELATIVE,
            position="top-left",
            margin_x=20,
            margin_y=30,
        )
        assert position.type == TextPositionType.RELATIVE
        assert position.position == "top-left"
        assert position.margin_x == 20
        assert position.margin_y == 30

    def test_text_position_invalid_position(self):
        """TextPosition валидирует неправильную позицию"""
        with pytest.raises(ValueError, match="Position must be one of"):
            TextPosition(position="invalid-position")

    def test_text_style_bounds(self):
        """TextStyle валидирует границы"""
        style = TextStyle(
            font_family="Roboto",
            font_size=50,
            font_weight="bold",
            color="#FF0000",
            alpha=0.8,
        )
        assert style.font_family == "Roboto"
        assert style.font_size == 50
        assert style.font_weight == "bold"
        assert style.color == "#FF0000"
        assert style.alpha == 0.8

    def test_text_style_invalid_size(self):
        """TextStyle валидирует размер шрифта"""
        with pytest.raises(ValueError):
            TextStyle(font_size=5)  # Ниже минимума

        with pytest.raises(ValueError):
            TextStyle(font_size=250)  # Выше максимума

    def test_text_style_invalid_weight(self):
        """TextStyle валидирует вес шрифта"""
        with pytest.raises(ValueError):
            TextStyle(font_weight="invalid")

    def test_text_style_invalid_color(self):
        """TextStyle валидирует цвет"""
        with pytest.raises(ValueError):
            TextStyle(color="red")  # Не hex формат

        with pytest.raises(ValueError):
            TextStyle(color="#FF00")  # Слишком короткий

    def test_text_style_invalid_alpha(self):
        """TextStyle валидирует alpha"""
        with pytest.raises(ValueError):
            TextStyle(alpha=-0.1)

        with pytest.raises(ValueError):
            TextStyle(alpha=1.5)

    def test_text_background_valid(self):
        """TextBackground валидирует параметры"""
        background = TextBackground(
            enabled=True,
            color="#000000",
            alpha=0.7,
            padding=15,
            border_radius=8,
        )
        assert background.enabled is True
        assert background.color == "#000000"
        assert background.alpha == 0.7
        assert background.padding == 15
        assert background.border_radius == 8

    def test_text_background_invalid_padding(self):
        """TextBackground валидирует padding"""
        with pytest.raises(ValueError):
            TextBackground(padding=-5)

    def test_text_border_valid(self):
        """TextBorder валидирует параметры"""
        border = TextBorder(
            enabled=True,
            width=3,
            color="#00FF00",
        )
        assert border.enabled is True
        assert border.width == 3
        assert border.color == "#00FF00"

    def test_text_border_invalid_width(self):
        """TextBorder валидирует width"""
        with pytest.raises(ValueError):
            TextBorder(width=-1)

    def test_text_shadow_valid(self):
        """TextShadow валидирует параметры"""
        shadow = TextShadow(
            enabled=True,
            offset_x=5,
            offset_y=-3,
            blur=4,
            color="#0000FF",
        )
        assert shadow.enabled is True
        assert shadow.offset_x == 5
        assert shadow.offset_y == -3
        assert shadow.blur == 4
        assert shadow.color == "#0000FF"

    def test_text_shadow_invalid_offset(self):
        """TextShadow валидирует offset"""
        with pytest.raises(ValueError):
            TextShadow(offset_x=100)

        with pytest.raises(ValueError):
            TextShadow(offset_y=-100)

    def test_text_shadow_invalid_blur(self):
        """TextShadow валидирует blur"""
        with pytest.raises(ValueError):
            TextShadow(blur=25)

    def test_text_animation_valid(self):
        """TextAnimation валидирует параметры"""
        animation = TextAnimation(
            type=TextAnimationType.FADE_IN,
            duration=2.5,
            delay=0.5,
        )
        assert animation.type == TextAnimationType.FADE_IN
        assert animation.duration == 2.5
        assert animation.delay == 0.5

    def test_text_animation_invalid_duration(self):
        """TextAnimation валидирует duration"""
        with pytest.raises(ValueError):
            TextAnimation(duration=-1.0)

    def test_text_overlay_request_full(self):
        """Полный TextOverlayRequest со всеми параметрами"""
        request = TextOverlayRequest(
            video_file_id=123,
            text="Hello World!",
            position=TextPosition(
                type=TextPositionType.RELATIVE,
                position="center",
                margin_x=50,
                margin_y=50,
            ),
            style=TextStyle(
                font_family="Arial",
                font_size=36,
                font_weight="bold",
                color="#FFFFFF",
                alpha=1.0,
            ),
            background=TextBackground(
                enabled=True,
                color="#000000",
                alpha=0.5,
                padding=20,
                border_radius=10,
            ),
            border=TextBorder(
                enabled=True,
                width=2,
                color="#FFFFFF",
            ),
            shadow=TextShadow(
                enabled=True,
                offset_x=2,
                offset_y=2,
                blur=3,
                color="#000000",
            ),
            animation=TextAnimation(
                type=TextAnimationType.FADE_IN,
                duration=1.0,
                delay=0.0,
            ),
            rotation=0,
            opacity=1.0,
            start_time=0.0,
            end_time=10.0,
            output_filename="output.mp4",
        )
        assert request.text == "Hello World!"
        assert request.position.position == "center"
        assert request.style.font_size == 36
        assert request.background.enabled is True
        assert request.border.enabled is True
        assert request.shadow.enabled is True
        assert request.animation.type == TextAnimationType.FADE_IN
        assert request.rotation == 0
        assert request.opacity == 1.0
        assert request.start_time == 0.0
        assert request.end_time == 10.0
        assert request.output_filename == "output.mp4"

    def test_text_overlay_request_invalid_text(self):
        """TextOverlayRequest валидирует пустой текст"""
        with pytest.raises(ValueError, match="Text cannot be empty"):
            TextOverlayRequest(video_file_id=1, text="")

        with pytest.raises(ValueError, match="Text cannot be empty"):
            TextOverlayRequest(video_file_id=1, text="   ")


class TestTextOverlayProcessor:
    """Unit тесты для TextOverlay processor"""

    @pytest.fixture
    def video_info(self):
        """Мок информации о видео"""
        return {
            "duration": 30.0,
            "width": 1920,
            "height": 1080,
            "video_codec": "h264",
            "fps": 30.0,
        }

    @pytest.fixture
    def mock_ffmpeg_command(self, video_info):
        """Мок FFmpegCommand"""
        with patch("app.processors.text_overlay.FFmpegCommand") as mock:
            mock.get_video_info = AsyncMock(return_value=video_info)
            mock.run_command = AsyncMock()
            yield mock

    @pytest.fixture
    def processor_config(self):
        """Конфигурация процессора"""
        return {
            "video_path": "/tmp/test_video.mp4",
            "text": "Test Text",
            "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
            "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
            "background": {"enabled": False, "color": "black", "alpha": 0.5, "padding": 10, "border_radius": 5},
            "border": {"enabled": False, "width": 2, "color": "black"},
            "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
            "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
            "rotation": 0,
            "opacity": 1.0,
            "start_time": 0.0,
            "end_time": None,
            "output_path": "/tmp/output.mp4",
        }

    def test_validate_input_valid_video(self, mock_ffmpeg_command, processor_config):
        """Валидация: проверка видео файла проходит"""
        processor = TextOverlay(task_id=1, config=processor_config)

        # Мок существования файла
        with patch("os.path.isfile", return_value=True):
            asyncio.run(processor.validate_input())

    def test_validate_input_missing_video(self, processor_config):
        """Валидация: видео файл не найден"""
        processor = TextOverlay(task_id=1, config=processor_config)

        with patch("os.path.isfile", return_value=False):
            with pytest.raises(FFmpegValidationError, match="Video file not found"):
                asyncio.run(processor.validate_input())

    def test_validate_input_empty_text(self, processor_config):
        """Валидация: пустой текст"""
        processor_config["text"] = ""
        processor = TextOverlay(task_id=1, config=processor_config)

        with patch("os.path.isfile", return_value=True):
            with pytest.raises(FFmpegValidationError, match="Text cannot be empty"):
                asyncio.run(processor.validate_input())

    def test_validate_invalid_start_time(self, mock_ffmpeg_command, processor_config):
        """Валидация: start_time больше длительности видео"""
        processor_config["start_time"] = 40.0
        processor = TextOverlay(task_id=1, config=processor_config)

        with patch("os.path.isfile", return_value=True):
            with pytest.raises(FFmpegValidationError, match="start_time.*must be less than"):
                asyncio.run(processor.validate_input())

    def test_validate_invalid_end_time(self, mock_ffmpeg_command, processor_config):
        """Валидация: end_time больше длительности видео"""
        processor_config["end_time"] = 40.0
        processor = TextOverlay(task_id=1, config=processor_config)

        with patch("os.path.isfile", return_value=True):
            with pytest.raises(FFmpegValidationError, match="end_time.*cannot exceed"):
                asyncio.run(processor.validate_input())

    def test_validate_invalid_time_range(self, mock_ffmpeg_command, processor_config):
        """Валидация: end_time <= start_time"""
        processor_config["start_time"] = 10.0
        processor_config["end_time"] = 5.0
        processor = TextOverlay(task_id=1, config=processor_config)

        with patch("os.path.isfile", return_value=True):
            with pytest.raises(FFmpegValidationError, match="end_time.*must be greater than"):
                asyncio.run(processor.validate_input())

    def test_calculate_position_absolute(self, processor_config):
        """Позиционирование: absolute координаты"""
        processor_config["position"] = {"type": "absolute", "x": 100, "y": 200}
        processor = TextOverlay(task_id=1, config=processor_config)
        pos = processor._calculate_position()
        assert pos == {"x": "100", "y": "200"}

    def test_calculate_position_relative_center(self, processor_config):
        """Позиционирование: relative center"""
        processor_config["position"] = {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10}
        processor = TextOverlay(task_id=1, config=processor_config)
        pos = processor._calculate_position()
        assert pos == {"x": "(w-tw)/2", "y": "(h-th)/2"}

    def test_calculate_position_relative_top_left(self, processor_config):
        """Позиционирование: relative top-left"""
        processor_config["position"] = {"type": "relative", "position": "top-left", "margin_x": 20, "margin_y": 30}
        processor = TextOverlay(task_id=1, config=processor_config)
        pos = processor._calculate_position()
        assert pos == {"x": "20", "y": "30"}

    def test_calculate_position_relative_bottom_right(self, processor_config):
        """Позиционирование: relative bottom-right"""
        processor_config["position"] = {"type": "relative", "position": "bottom-right", "margin_x": 15, "margin_y": 20}
        processor = TextOverlay(task_id=1, config=processor_config)
        pos = processor._calculate_position()
        assert pos == {"x": "w-tw-15", "y": "h-th-20"}

    def test_get_relative_position_all_9_positions(self, processor_config):
        """Позиционирование: все 9 позиций"""
        processor_config["position"] = {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10}
        processor = TextOverlay(task_id=1, config=processor_config)

        positions = [
            ("top-left", {"x": "10", "y": "10"}),
            ("top-center", {"x": "(w-tw)/2", "y": "10"}),
            ("top-right", {"x": "w-tw-10", "y": "10"}),
            ("center-left", {"x": "10", "y": "(h-th)/2"}),
            ("center", {"x": "(w-tw)/2", "y": "(h-th)/2"}),
            ("center-right", {"x": "w-tw-10", "y": "(h-th)/2"}),
            ("bottom-left", {"x": "10", "y": "h-th-10"}),
            ("bottom-center", {"x": "(w-tw)/2", "y": "h-th-10"}),
            ("bottom-right", {"x": "w-tw-10", "y": "h-th-10"}),
        ]

        for position, expected in positions:
            processor_config["position"]["position"] = position
            processor = TextOverlay(task_id=1, config=processor_config)
            result = processor._calculate_position()
            assert result == expected, f"Failed for position: {position}"

    def test_generate_drawtext_filter(self, processor_config):
        """Генерация drawtext фильтра"""
        processor = TextOverlay(task_id=1, config=processor_config)
        filter_str = processor._generate_drawtext_filter()
        assert filter_str.startswith("drawtext=")
        assert "text=Test%20Text" in filter_str or "text='Test%20Text'" in filter_str
        assert "fontsize=24" in filter_str

    def test_escape_text_special_chars(self, processor_config):
        """Экранирование текста"""
        processor = TextOverlay(task_id=1, config=processor_config)
        processor_config["text"] = "Hello: World! [test]"
        escaped = processor._escape_text("Hello: World! [test]")
        assert "\\:" in escaped
        assert "\\[" in escaped
        assert "\\]" in escaped

    def test_escape_text_quotes(self, processor_config):
        """Экранирование кавычек"""
        processor = TextOverlay(task_id=1, config=processor_config)
        escaped = processor._escape_text("Don't worry")
        assert "'\\''" in escaped

    def test_color_to_hex(self, processor_config):
        """Конвертация цвета из #RRGGBB в FFmpeg format"""
        processor = TextOverlay(task_id=1, config=processor_config)
        result = processor._color_to_hex("#FF0000", 1.0)
        assert result == "&HFF0000FF&"  # &HBBGGRR& format

    def test_color_to_hex_with_alpha(self, processor_config):
        """Конвертация цвета с alpha"""
        processor = TextOverlay(task_id=1, config=processor_config)
        result = processor._color_to_hex("#00FF00", 0.5)
        # Alpha 0.5 * 255 = 127 (rounded)
        assert result.startswith("&H")
        assert "00FF00" in result  # Green component
        assert "&" in result

    def test_build_background_params_disabled(self, processor_config):
        """Background параметры: выключен"""
        processor = TextOverlay(task_id=1, config=processor_config)
        params = processor._build_background_params({"enabled": False})
        assert params == []

    def test_build_background_params_enabled(self, processor_config):
        """Background параметры: включен"""
        processor = TextOverlay(task_id=1, config=processor_config)
        background = {
            "enabled": True,
            "color": "#000000",
            "alpha": 0.7,
            "padding": 15,
            "border_radius": 5,
        }
        params = processor._build_background_params(background)
        assert "box=1" in params
        assert "boxcolor=" in params
        assert "boxborderw=15" in params
        assert "boxradius=5" in params

    def test_build_border_params_disabled(self, processor_config):
        """Border параметры: выключен"""
        processor = TextOverlay(task_id=1, config=processor_config)
        params = processor._build_border_params({"enabled": False})
        assert params == []

    def test_build_border_params_enabled(self, processor_config):
        """Border параметры: включен"""
        processor = TextOverlay(task_id=1, config=processor_config)
        border = {
            "enabled": True,
            "width": 3,
            "color": "#FFFFFF",
        }
        params = processor._build_border_params(border)
        assert "borderw=3" in params
        assert "bordercolor=" in params

    def test_build_shadow_params_disabled(self, processor_config):
        """Shadow параметры: выключен"""
        processor = TextOverlay(task_id=1, config=processor_config)
        params = processor._build_shadow_params({"enabled": False})
        assert params == []

    def test_build_shadow_params_enabled(self, processor_config):
        """Shadow параметры: включен"""
        processor = TextOverlay(task_id=1, config=processor_config)
        shadow = {
            "enabled": True,
            "offset_x": 5,
            "offset_y": -3,
            "blur": 4,
            "color": "#000000",
        }
        params = processor._build_shadow_params(shadow)
        assert "shadowx=5" in params
        assert "shadowy=-3" in params
        assert "shadowcolor=" in params
        assert "shadoww=4" in params

    def test_build_animation_params_none(self, processor_config):
        """Анимация: none"""
        processor = TextOverlay(task_id=1, config=processor_config)
        params = processor._build_animation_params({"type": "none"}, 0.0, None)
        assert params == []

    def test_build_animation_params_fade_in(self, processor_config):
        """Анимация: fade in"""
        processor = TextOverlay(task_id=1, config=processor_config)
        animation = {"type": "fade_in", "duration": 2.0, "delay": 1.0}
        params = processor._build_animation_params(animation, 0.0, 10.0)
        assert any("enable=" in p for p in params)
        assert any("alpha=" in p for p in params)

    def test_build_animation_params_fade_out(self, processor_config):
        """Анимация: fade out"""
        processor = TextOverlay(task_id=1, config=processor_config)
        animation = {"type": "fade_out", "duration": 1.5, "delay": 0.5}
        params = processor._build_animation_params(animation, 0.0, 10.0)
        assert any("enable=" in p for p in params)

    def test_build_animation_params_slide_left(self, processor_config):
        """Анимация: slide left"""
        processor = TextOverlay(task_id=1, config=processor_config)
        animation = {"type": "slide_left", "duration": 2.0, "delay": 0.0}
        params = processor._build_animation_params(animation, 0.0, 10.0)
        assert any("enable=" in p for p in params)
        assert any("x=" in p for p in params)

    def test_build_drawtext_params_full(self, processor_config):
        """Построение всех параметров drawtext"""
        processor_config["background"] = {"enabled": True, "color": "#000000", "alpha": 0.5, "padding": 15, "border_radius": 5}
        processor_config["border"] = {"enabled": True, "width": 2, "color": "#FFFFFF"}
        processor_config["shadow"] = {"enabled": True, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "#000000"}
        processor_config["rotation"] = 15
        processor_config["opacity"] = 0.9

        processor = TextOverlay(task_id=1, config=processor_config)
        params = processor._build_drawtext_params()

        assert "text=Test%20Text" in params or "text='Test%20Text'" in params
        assert "fontsize=24" in params
        assert "fontcolor=" in params
        assert "x=" in params
        assert "y=" in params
        assert "box=1" in params
        assert "borderw=2" in params
        assert "shadowx=2" in params
        assert "rotation=15" in params
        assert "alpha='0.9'" in params or "alpha=0.9" in params

    def test_process_success(self, mock_ffmpeg_command, processor_config):
        """Успешная обработка"""
        processor = TextOverlay(task_id=1, config=processor_config)

        with patch("os.path.isfile", return_value=True):
            result = asyncio.run(processor.run())
            assert "output_path" in result
            assert result["output_path"] == "/tmp/output.mp4"

    def test_process_creates_temp_file(self, mock_ffmpeg_command, processor_config):
        """Создание временного файла если output_path не указан"""
        processor_config.pop("output_path", None)
        processor = TextOverlay(task_id=1, config=processor_config)

        with patch("os.path.isfile", return_value=True):
            with patch("app.processors.text_overlay.create_temp_file") as mock_temp:
                mock_temp.return_value = "/tmp/temp_output.mp4"
                result = asyncio.run(processor.run())
                assert "output_path" in result
                mock_temp.assert_called_once()

    def test_progress_callback(self, mock_ffmpeg_command, processor_config):
        """Progress callback вызывается"""
        progress_updates = []

        def progress_cb(p):
            progress_updates.append(p)

        processor = TextOverlay(task_id=1, config=processor_config, progress_callback=progress_cb)

        with patch("os.path.isfile", return_value=True):
            asyncio.run(processor.run())
            assert len(progress_updates) > 0
            assert 100.0 in progress_updates


class TestTextOverlayIntegration:
    """Интеграционные тесты для TextOverlay"""

    @pytest.fixture
    def video_info(self):
        return {
            "duration": 30.0,
            "width": 1920,
            "height": 1080,
            "video_codec": "h264",
            "fps": 30.0,
        }

    @pytest.fixture
    def mock_ffmpeg(self, video_info):
        with patch("app.processors.text_overlay.FFmpegCommand") as mock:
            mock.get_video_info = AsyncMock(return_value=video_info)
            mock.run_command = AsyncMock()
            yield mock

    def test_basic_text_overlay(self, mock_ffmpeg):
        """Базовый текст без стилей"""
        config = {
            "video_path": "/tmp/video.mp4",
            "text": "Hello World!",
            "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
            "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
            "background": {"enabled": False, "color": "black", "alpha": 0.5, "padding": 10, "border_radius": 5},
            "border": {"enabled": False, "width": 2, "color": "black"},
            "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
            "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
            "rotation": 0,
            "opacity": 1.0,
            "start_time": 0.0,
            "end_time": None,
            "output_path": "/tmp/output.mp4",
        }

        processor = TextOverlay(task_id=1, config=config)
        with patch("os.path.isfile", return_value=True):
            result = asyncio.run(processor.run())
            assert "output_path" in result

    def test_text_with_styles(self, mock_ffmpeg):
        """Текст со стилями"""
        config = {
            "video_path": "/tmp/video.mp4",
            "text": "Styled Text",
            "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
            "style": {"font_family": "Roboto", "font_size": 48, "font_weight": "bold", "color": "#FF0000", "alpha": 0.9},
            "background": {"enabled": False, "color": "black", "alpha": 0.5, "padding": 10, "border_radius": 5},
            "border": {"enabled": False, "width": 2, "color": "black"},
            "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
            "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
            "rotation": 0,
            "opacity": 1.0,
            "start_time": 0.0,
            "end_time": None,
            "output_path": "/tmp/output.mp4",
        }

        processor = TextOverlay(task_id=1, config=config)
        with patch("os.path.isfile", return_value=True):
            filter_str = processor._generate_drawtext_filter()
            assert "fontsize=48" in filter_str
            assert "Roboto" in filter_str

    def test_text_with_background(self, mock_ffmpeg):
        """Текст с background"""
        config = {
            "video_path": "/tmp/video.mp4",
            "text": "Text with BG",
            "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
            "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
            "background": {"enabled": True, "color": "#000000", "alpha": 0.7, "padding": 20, "border_radius": 10},
            "border": {"enabled": False, "width": 2, "color": "black"},
            "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
            "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
            "rotation": 0,
            "opacity": 1.0,
            "start_time": 0.0,
            "end_time": None,
            "output_path": "/tmp/output.mp4",
        }

        processor = TextOverlay(task_id=1, config=config)
        with patch("os.path.isfile", return_value=True):
            filter_str = processor._generate_drawtext_filter()
            assert "box=1" in filter_str
            assert "boxborderw=20" in filter_str
            assert "boxradius=10" in filter_str

    def test_text_with_border(self, mock_ffmpeg):
        """Текст с border"""
        config = {
            "video_path": "/tmp/video.mp4",
            "text": "Bordered Text",
            "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
            "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
            "background": {"enabled": False, "color": "black", "alpha": 0.5, "padding": 10, "border_radius": 5},
            "border": {"enabled": True, "width": 3, "color": "#00FF00"},
            "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
            "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
            "rotation": 0,
            "opacity": 1.0,
            "start_time": 0.0,
            "end_time": None,
            "output_path": "/tmp/output.mp4",
        }

        processor = TextOverlay(task_id=1, config=config)
        with patch("os.path.isfile", return_value=True):
            filter_str = processor._generate_drawtext_filter()
            assert "borderw=3" in filter_str
            assert "bordercolor=" in filter_str

    def test_text_with_shadow(self, mock_ffmpeg):
        """Текст с shadow"""
        config = {
            "video_path": "/tmp/video.mp4",
            "text": "Shadowed Text",
            "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
            "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
            "background": {"enabled": False, "color": "black", "alpha": 0.5, "padding": 10, "border_radius": 5},
            "border": {"enabled": False, "width": 2, "color": "black"},
            "shadow": {"enabled": True, "offset_x": 5, "offset_y": 5, "blur": 4, "color": "#000000"},
            "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
            "rotation": 0,
            "opacity": 1.0,
            "start_time": 0.0,
            "end_time": None,
            "output_path": "/tmp/output.mp4",
        }

        processor = TextOverlay(task_id=1, config=config)
        with patch("os.path.isfile", return_value=True):
            filter_str = processor._generate_drawtext_filter()
            assert "shadowx=5" in filter_str
            assert "shadowy=5" in filter_str
            assert "shadoww=4" in filter_str

    def test_text_with_fade_animation(self, mock_ffmpeg):
        """Текст с fade анимацией"""
        config = {
            "video_path": "/tmp/video.mp4",
            "text": "Fade Text",
            "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
            "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
            "background": {"enabled": False, "color": "black", "alpha": 0.5, "padding": 10, "border_radius": 5},
            "border": {"enabled": False, "width": 2, "color": "black"},
            "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
            "animation": {"type": "fade_in", "duration": 2.0, "delay": 0.5},
            "rotation": 0,
            "opacity": 1.0,
            "start_time": 0.0,
            "end_time": None,
            "output_path": "/tmp/output.mp4",
        }

        processor = TextOverlay(task_id=1, config=config)
        with patch("os.path.isfile", return_value=True):
            filter_str = processor._generate_drawtext_filter()
            assert "enable=" in filter_str
            assert "alpha=" in filter_str

    def test_text_with_rotation(self, mock_ffmpeg):
        """Текст с rotation"""
        config = {
            "video_path": "/tmp/video.mp4",
            "text": "Rotated Text",
            "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
            "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
            "background": {"enabled": False, "color": "black", "alpha": 0.5, "padding": 10, "border_radius": 5},
            "border": {"enabled": False, "width": 2, "color": "black"},
            "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
            "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
            "rotation": 45,
            "opacity": 1.0,
            "start_time": 0.0,
            "end_time": None,
            "output_path": "/tmp/output.mp4",
        }

        processor = TextOverlay(task_id=1, config=config)
        with patch("os.path.isfile", return_value=True):
            filter_str = processor._generate_drawtext_filter()
            assert "rotation=45" in filter_str

    def test_multiline_text(self, mock_ffmpeg):
        """Многострочный текст"""
        config = {
            "video_path": "/tmp/video.mp4",
            "text": "Line 1\nLine 2\nLine 3",
            "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
            "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
            "background": {"enabled": False, "color": "black", "alpha": 0.5, "padding": 10, "border_radius": 5},
            "border": {"enabled": False, "width": 2, "color": "black"},
            "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
            "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
            "rotation": 0,
            "opacity": 1.0,
            "start_time": 0.0,
            "end_time": None,
            "output_path": "/tmp/output.mp4",
        }

        processor = TextOverlay(task_id=1, config=config)
        with patch("os.path.isfile", return_value=True):
            filter_str = processor._generate_drawtext_filter()
            assert "text=" in filter_str

    def test_all_features_combined(self, mock_ffmpeg):
        """Все функции вместе"""
        config = {
            "video_path": "/tmp/video.mp4",
            "text": "Full Featured Text",
            "position": {"type": "relative", "position": "center", "margin_x": 50, "margin_y": 50},
            "style": {"font_family": "Arial", "font_size": 36, "font_weight": "bold", "color": "#FFFFFF", "alpha": 0.95},
            "background": {"enabled": True, "color": "#000000", "alpha": 0.6, "padding": 25, "border_radius": 15},
            "border": {"enabled": True, "width": 2, "color": "#FF0000"},
            "shadow": {"enabled": True, "offset_x": 4, "offset_y": 4, "blur": 5, "color": "#000000"},
            "animation": {"type": "fade_in", "duration": 1.5, "delay": 0.3},
            "rotation": 0,
            "opacity": 0.9,
            "start_time": 2.0,
            "end_time": 8.0,
            "output_path": "/tmp/output.mp4",
        }

        processor = TextOverlay(task_id=1, config=config)
        with patch("os.path.isfile", return_value=True):
            filter_str = processor._generate_drawtext_filter()
            assert "text=" in filter_str
            assert "fontsize=36" in filter_str
            assert "box=1" in filter_str
            assert "borderw=2" in filter_str
            assert "shadowx=4" in filter_str
            assert "alpha=" in filter_str
            assert "enable=" in filter_str
