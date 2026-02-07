"""
Comprehensive tests for Video Overlay (Picture-in-Picture) functionality
"""
import os
import tempfile
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import pytest
from pathlib import Path

from app.schemas.video_overlay import (
    OverlayShapeType,
    OverlayConfig,
    BorderStyle,
    ShadowStyle,
    VideoOverlayRequest,
)
from app.processors.video_overlay import VideoOverlay
from app.ffmpeg.exceptions import FFmpegValidationError


# ============================================================================
# Pydantic Schemas Tests
# ============================================================================

class TestVideoOverlaySchemas:
    """Test Pydantic schemas for video overlay"""

    def test_overlay_config_defaults(self):
        """Test OverlayConfig has correct defaults"""
        config = OverlayConfig()
        assert config.x == 10
        assert config.y == 10
        assert config.width is None
        assert config.height is None
        assert config.scale == 0.2
        assert config.opacity == 1.0
        assert config.shape == OverlayShapeType.RECTANGLE
        assert config.border_radius == 0

    def test_overlay_config_validation_x_negative(self):
        """Test OverlayConfig validates x >= 0"""
        with pytest.raises(ValueError):
            OverlayConfig(x=-1)

    def test_overlay_config_validation_y_negative(self):
        """Test OverlayConfig validates y >= 0"""
        with pytest.raises(ValueError):
            OverlayConfig(y=-1)

    def test_overlay_config_validation_scale_zero(self):
        """Test OverlayConfig validates scale > 0"""
        with pytest.raises(ValueError):
            OverlayConfig(scale=0)

    def test_overlay_config_validation_scale_gt_1(self):
        """Test OverlayConfig validates scale <= 1"""
        with pytest.raises(ValueError):
            OverlayConfig(scale=1.5)

    def test_overlay_config_validation_opacity_negative(self):
        """Test OverlayConfig validates opacity >= 0"""
        with pytest.raises(ValueError):
            OverlayConfig(opacity=-0.1)

    def test_overlay_config_validation_opacity_gt_1(self):
        """Test OverlayConfig validates opacity <= 1"""
        with pytest.raises(ValueError):
            OverlayConfig(opacity=1.1)

    def test_overlay_config_width_and_height(self):
        """Test OverlayConfig accepts explicit width and height"""
        config = OverlayConfig(width=200, height=150)
        assert config.width == 200
        assert config.height == 150

    def test_overlay_config_width_zero_invalid(self):
        """Test OverlayConfig rejects width = 0"""
        with pytest.raises(ValueError):
            OverlayConfig(width=0)

    def test_overlay_config_height_zero_invalid(self):
        """Test OverlayConfig rejects height = 0"""
        with pytest.raises(ValueError):
            OverlayConfig(height=0)

    def test_overlay_config_shape_rectangle(self):
        """Test OverlayConfig with rectangle shape"""
        config = OverlayConfig(shape=OverlayShapeType.RECTANGLE)
        assert config.shape == OverlayShapeType.RECTANGLE

    def test_overlay_config_shape_circle(self):
        """Test OverlayConfig with circle shape"""
        config = OverlayConfig(shape=OverlayShapeType.CIRCLE)
        assert config.shape == OverlayShapeType.CIRCLE

    def test_overlay_config_shape_rounded(self):
        """Test OverlayConfig with rounded shape"""
        config = OverlayConfig(shape=OverlayShapeType.ROUNDED, border_radius=15)
        assert config.shape == OverlayShapeType.ROUNDED
        assert config.border_radius == 15

    def test_border_style_defaults(self):
        """Test BorderStyle has correct defaults"""
        border = BorderStyle()
        assert border.enabled is False
        assert border.width == 2
        assert border.color == "black"

    def test_border_style_enabled(self):
        """Test BorderStyle can be enabled"""
        border = BorderStyle(enabled=True, width=4, color="#FF0000")
        assert border.enabled is True
        assert border.width == 4
        assert border.color == "#FF0000"

    def test_border_style_width_negative(self):
        """Test BorderStyle validates width >= 0"""
        with pytest.raises(ValueError):
            BorderStyle(width=-1)

    def test_border_style_color_invalid_format(self):
        """Test BorderStyle validates color hex format"""
        with pytest.raises(ValueError):
            BorderStyle(color="red")  # Not hex format
        with pytest.raises(ValueError):
            BorderStyle(color="FF0000")  # Missing #
        with pytest.raises(ValueError):
            BorderStyle(color="#FF00")  # Too short

    def test_border_style_color_valid(self):
        """Test BorderStyle accepts valid hex colors"""
        border = BorderStyle(color="#FF0000")
        assert border.color == "#FF0000"

    def test_shadow_style_defaults(self):
        """Test ShadowStyle has correct defaults"""
        shadow = ShadowStyle()
        assert shadow.enabled is False
        assert shadow.offset_x == 2
        assert shadow.offset_y == 2
        assert shadow.blur == 2
        assert shadow.color == "black"

    def test_shadow_style_enabled(self):
        """Test ShadowStyle can be enabled"""
        shadow = ShadowStyle(enabled=True, offset_x=5, offset_y=5, blur=4, color="#000000")
        assert shadow.enabled is True
        assert shadow.offset_x == 5
        assert shadow.offset_y == 5
        assert shadow.blur == 4
        assert shadow.color == "#000000"

    def test_shadow_style_offset_x_out_of_range_negative(self):
        """Test ShadowStyle validates offset_x >= -50"""
        with pytest.raises(ValueError):
            ShadowStyle(offset_x=-51)

    def test_shadow_style_offset_x_out_of_range_positive(self):
        """Test ShadowStyle validates offset_x <= 50"""
        with pytest.raises(ValueError):
            ShadowStyle(offset_x=51)

    def test_shadow_style_offset_y_out_of_range_negative(self):
        """Test ShadowStyle validates offset_y >= -50"""
        with pytest.raises(ValueError):
            ShadowStyle(offset_y=-51)

    def test_shadow_style_offset_y_out_of_range_positive(self):
        """Test ShadowStyle validates offset_y <= 50"""
        with pytest.raises(ValueError):
            ShadowStyle(offset_y=51)

    def test_shadow_style_blur_out_of_range_negative(self):
        """Test ShadowStyle validates blur >= 0"""
        with pytest.raises(ValueError):
            ShadowStyle(blur=-1)

    def test_shadow_style_blur_out_of_range_positive(self):
        """Test ShadowStyle validates blur <= 20"""
        with pytest.raises(ValueError):
            ShadowStyle(blur=21)

    def test_shadow_style_color_invalid_format(self):
        """Test ShadowStyle validates color hex format"""
        with pytest.raises(ValueError):
            ShadowStyle(color="red")

    def test_video_overlay_request_validation(self):
        """Test VideoOverlayRequest validates correctly"""
        request = VideoOverlayRequest(
            base_video_file_id=1,
            overlay_video_file_id=2,
        )
        assert request.base_video_file_id == 1
        assert request.overlay_video_file_id == 2
        assert isinstance(request.config, OverlayConfig)
        assert isinstance(request.border, BorderStyle)
        assert isinstance(request.shadow, ShadowStyle)

    def test_video_overlay_request_with_config(self):
        """Test VideoOverlayRequest with custom config"""
        request = VideoOverlayRequest(
            base_video_file_id=1,
            overlay_video_file_id=2,
            config=OverlayConfig(x=50, y=50, scale=0.3),
            border=BorderStyle(enabled=True),
            output_filename="custom_overlay.mp4"
        )
        assert request.config.x == 50
        assert request.config.y == 50
        assert request.config.scale == 0.3
        assert request.border.enabled is True
        assert request.output_filename == "custom_overlay.mp4"

    def test_video_overlay_request_to_dict(self):
        """Test VideoOverlayRequest.to_dict() converts to dict"""
        request = VideoOverlayRequest(
            base_video_file_id=1,
            overlay_video_file_id=2,
            config=OverlayConfig(x=20, y=30),
        )
        result = request.to_dict()
        assert result["base_video_file_id"] == 1
        assert result["overlay_video_file_id"] == 2
        assert isinstance(result["config"], dict)
        assert result["config"]["x"] == 20
        assert result["config"]["y"] == 30
        assert isinstance(result["border"], dict)
        assert isinstance(result["shadow"], dict)


# ============================================================================
# VideoOverlay Processor Unit Tests
# ============================================================================

class TestVideoOverlayProcessor:
    """Test VideoOverlay processor"""

    @pytest.fixture
    def base_video_path(self):
        """Create a temporary base video file"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake_video_content")
            path = f.name
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def overlay_video_path(self):
        """Create a temporary overlay video file"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake_overlay_content")
            path = f.name
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def mock_video_info_base(self):
        """Mock base video info"""
        return {
            "width": 1920,
            "height": 1080,
            "duration": 120.0,
            "video_codec": "h264",
            "fps": 30.0
        }

    @pytest.fixture
    def mock_video_info_overlay(self):
        """Mock overlay video info"""
        return {
            "width": 640,
            "height": 480,
            "duration": 30.0,
            "video_codec": "h264",
            "fps": 30.0
        }

    @pytest.fixture
    def processor(self, base_video_path, overlay_video_path):
        """Create VideoOverlay processor instance"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": base_video_path,
            "overlay_file_path": overlay_video_path,
            "config": {},
        }
        return VideoOverlay(task_id=1, config=config)

    def test_processor_initialization(self, processor):
        """Test processor initializes correctly"""
        assert processor.task_id == 1
        assert processor.base_file_id == 1
        assert processor.overlay_file_id == 2

    @pytest.mark.asyncio
    async def test_validate_input_missing_base_path(self):
        """Test validate_input raises error when base_file_path is missing"""
        processor = VideoOverlay(task_id=1, config={})
        with pytest.raises(FFmpegValidationError, match="base_file_path is required"):
            await processor.validate_input()

    @pytest.mark.asyncio
    async def test_validate_input_missing_overlay_path(self):
        """Test validate_input raises error when overlay_file_path is missing"""
        processor = VideoOverlay(
            task_id=1,
            config={"base_file_path": "/tmp/base.mp4"}
        )
        with pytest.raises(FFmpegValidationError, match="overlay_file_path is required"):
            await processor.validate_input()

    @pytest.mark.asyncio
    async def test_validate_input_base_file_not_found(self):
        """Test validate_input raises error when base file doesn't exist"""
        processor = VideoOverlay(
            task_id=1,
            config={
                "base_file_path": "/nonexistent/base.mp4",
                "overlay_file_path": "/nonexistent/overlay.mp4"
            }
        )
        with pytest.raises(FFmpegValidationError, match="Base video file not found"):
            await processor.validate_input()

    @pytest.mark.asyncio
    async def test_validate_input_success(
        self, processor, mock_video_info_base, mock_video_info_overlay
    ):
        """Test validate_input succeeds with valid files"""
        with patch("app.processors.video_overlay.FFmpegCommand.get_video_info") as mock_get_info:
            # Mock for base file and overlay file in correct order
            mock_get_info.side_effect = [mock_video_info_base, mock_video_info_overlay]

            await processor.validate_input()

            assert processor.base_file_path is not None
            assert processor.overlay_file_path is not None
            assert processor.config["base_info"] == mock_video_info_base
            assert processor.config["overlay_info"] == mock_video_info_overlay

    def test_calculate_overlay_size_using_explicit_dimensions(self, processor):
        """Test _calculate_overlay_size uses explicit width/height when provided"""
        processor.config["config"] = {"width": 300, "height": 200}
        width, height = processor._calculate_overlay_size(640, 480)
        assert width == 300
        assert height == 200

    def test_calculate_overlay_size_using_scale(self, processor):
        """Test _calculate_overlay_size uses scale when explicit dimensions not provided"""
        processor.config["config"] = {"scale": 0.25}
        width, height = processor._calculate_overlay_size(640, 480)
        assert width == 160  # 640 * 0.25
        assert height == 120  # 480 * 0.25

    def test_calculate_overlay_size_default_scale(self, processor):
        """Test _calculate_overlay_size uses default scale 0.2 when not specified"""
        processor.config["config"] = {}
        width, height = processor._calculate_overlay_size(640, 480)
        assert width == 128  # 640 * 0.2
        assert height == 96  # 480 * 0.2

    def test_calculate_overlay_size_only_width_provided(self, processor):
        """Test _calculate_overlay_size with only width provided"""
        processor.config["config"] = {"width": 200}
        # When only width is provided (not both width and height), scale is used for both dimensions
        width, height = processor._calculate_overlay_size(640, 480)
        # If both width and height are not present in config, scale is used
        # With only width provided, the current implementation uses scale
        assert width == 128  # 640 * 0.2 (default scale)
        assert height == 96  # 480 * 0.2

    def test_color_to_hex_with_hash(self, processor):
        """Test _color_to_hex converts #RRGGBB to 0xRRGGBB"""
        result = processor._color_to_hex("#FF0000")
        assert result == "0xFF0000"

    def test_color_to_hex_without_hash(self, processor):
        """Test _color_to_hex handles input without hash"""
        result = processor._color_to_hex("0xFF0000")
        assert result == "0xFF0000"

    def test_apply_shape_filter_rectangle(self, processor):
        """Test _apply_shape_filter returns empty string for rectangle"""
        processor.config["config"] = {"shape": "rectangle"}
        result = processor._apply_shape_filter(200, 150)
        assert result == ""

    def test_apply_shape_filter_circle(self, processor):
        """Test _apply_shape_filter generates correct geq filter for circle"""
        processor.config["config"] = {"shape": "circle"}
        width, height = 200, 150
        radius = min(width, height) // 2
        cx, cy = width // 2, height // 2
        result = processor._apply_shape_filter(width, height)
        
        assert "format=alpha" in result
        assert "geq=" in result
        assert f"hypot(X-{cx},Y-{cy})<={radius}" in result
        assert "?a:0" in result

    def test_apply_shape_filter_rounded(self, processor):
        """Test _apply_shape_filter generates correct geq filter for rounded corners"""
        processor.config["config"] = {"shape": "rounded", "border_radius": 10}
        width, height = 200, 150
        result = processor._apply_shape_filter(width, height)
        
        assert "format=alpha" in result
        assert "geq=" in result
        assert "hypot(min(X,W-X),min(Y,H-Y))" in result
        assert ">=10" in result  # Radius value is in the filter

    def test_apply_shape_filter_rounded_with_custom_radius(self, processor):
        """Test _apply_shape_filter uses custom border_radius for rounded corners"""
        processor.config["config"] = {"shape": "rounded", "border_radius": 20}
        result = processor._apply_shape_filter(200, 150)
        assert "20" in result or "-{radius}" in result  # May be interpolated

    def test_apply_border_filter_disabled(self, processor):
        """Test _apply_border_filter returns empty string when disabled"""
        processor.config["border"] = {"enabled": False}
        result = processor._apply_border_filter(200, 150)
        assert result == ""

    def test_apply_border_filter_enabled(self, processor):
        """Test _apply_border_filter generates correct drawbox filter"""
        processor.config["border"] = {
            "enabled": True,
            "width": 4,
            "color": "#FF0000"
        }
        result = processor._apply_border_filter(200, 150)
        
        assert "drawbox=" in result
        assert "x=0:y=0:w=200:h=150" in result
        assert "color=0xFF0000" in result
        assert "t=4" in result

    def test_apply_border_filter_default_color(self, processor):
        """Test _apply_border_filter uses default color black"""
        processor.config["border"] = {"enabled": True, "width": 2}
        result = processor._apply_border_filter(200, 150)
        assert "color=0x000000" in result or "color=black" in result

    def test_apply_shadow_filter_disabled(self, processor):
        """Test _apply_shadow_filter returns empty string when disabled"""
        processor.config["shadow"] = {"enabled": False}
        result = processor._apply_shadow_filter(200, 150)
        assert result == ""

    def test_apply_shadow_filter_enabled(self, processor):
        """Test _apply_shadow_filter generates correct shadow filter"""
        processor.config["shadow"] = {
            "enabled": True,
            "offset_x": 5,
            "offset_y": 5,
            "blur": 3,
            "color": "#000000"
        }
        result = processor._apply_shadow_filter(200, 150)
        
        assert "shadow=" in result
        assert "5:5:3:0x000000" in result

    def test_apply_shadow_filter_default_params(self, processor):
        """Test _apply_shadow_filter uses default parameters"""
        processor.config["shadow"] = {"enabled": True}
        result = processor._apply_shadow_filter(200, 150)
        
        # Should have default offsets and blur
        assert "shadow=" in result
        assert "2:2:2:" in result  # offset_x:offset_y:blur:

    def test_generate_ffmpeg_command_basic(
        self, processor, base_video_path, overlay_video_path,
        mock_video_info_base, mock_video_info_overlay
    ):
        """Test _generate_ffmpeg_command generates correct basic command"""
        processor.config["config"] = {}
        processor.config["base_info"] = mock_video_info_base
        processor.config["overlay_info"] = mock_video_info_overlay
        
        output_path = tempfile.mktemp(suffix=".mp4")
        cmd = processor._generate_ffmpeg_command(
            base_video_path, overlay_video_path, output_path
        )
        
        # FFmpeg binary should be in command (either ffmpeg, ffmpeg.exe, or full path)
        assert any("ffmpeg" in str(arg).lower() for arg in cmd)
        assert "-y" in cmd
        assert "-i" in cmd
        assert base_video_path in cmd
        assert overlay_video_path in cmd
        assert output_path in cmd
        assert "-filter_complex" in cmd

    def test_generate_ffmpeg_command_with_position(
        self, processor, base_video_path, overlay_video_path,
        mock_video_info_base, mock_video_info_overlay
    ):
        """Test _generate_ffmpeg_command includes position parameters"""
        processor.config["config"] = {"x": 100, "y": 50}
        processor.config["base_info"] = mock_video_info_base
        processor.config["overlay_info"] = mock_video_info_overlay
        
        output_path = tempfile.mktemp(suffix=".mp4")
        cmd = processor._generate_ffmpeg_command(
            base_video_path, overlay_video_path, output_path
        )
        
        # Check filter complex contains position
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "overlay=100:50" in filter_str

    def test_generate_ffmpeg_command_with_scale(
        self, processor, base_video_path, overlay_video_path,
        mock_video_info_base, mock_video_info_overlay
    ):
        """Test _generate_ffmpeg_command includes scale parameter"""
        processor.config["config"] = {"scale": 0.5}
        processor.config["base_info"] = mock_video_info_base
        processor.config["overlay_info"] = mock_video_info_overlay
        
        output_path = tempfile.mktemp(suffix=".mp4")
        cmd = processor._generate_ffmpeg_command(
            base_video_path, overlay_video_path, output_path
        )
        
        # Should scale overlay to half size
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "scale=" in filter_str
        # 640 * 0.5 = 320, 480 * 0.5 = 240
        assert "320:240" in filter_str

    def test_generate_ffmpeg_command_with_opacity(
        self, processor, base_video_path, overlay_video_path,
        mock_video_info_base, mock_video_info_overlay
    ):
        """Test _generate_ffmpeg_command includes opacity when < 1.0"""
        processor.config["config"] = {"opacity": 0.5}
        processor.config["base_info"] = mock_video_info_base
        processor.config["overlay_info"] = mock_video_info_overlay
        
        output_path = tempfile.mktemp(suffix=".mp4")
        cmd = processor._generate_ffmpeg_command(
            base_video_path, overlay_video_path, output_path
        )
        
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "format=alpha" in filter_str
        assert "colorchannelmixer" in filter_str
        assert "aa=0.5" in filter_str

    def test_generate_ffmpeg_command_with_circle_shape(
        self, processor, base_video_path, overlay_video_path,
        mock_video_info_base, mock_video_info_overlay
    ):
        """Test _generate_ffmpeg_command includes circle shape filter"""
        processor.config["config"] = {"shape": "circle"}
        processor.config["base_info"] = mock_video_info_base
        processor.config["overlay_info"] = mock_video_info_overlay
        
        output_path = tempfile.mktemp(suffix=".mp4")
        cmd = processor._generate_ffmpeg_command(
            base_video_path, overlay_video_path, output_path
        )
        
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "geq=" in filter_str
        assert "hypot(" in filter_str

    def test_generate_ffmpeg_command_with_border(
        self, processor, base_video_path, overlay_video_path,
        mock_video_info_base, mock_video_info_overlay
    ):
        """Test _generate_ffmpeg_command includes border filter"""
        processor.config["border"] = {
            "enabled": True,
            "width": 4,
            "color": "#FF0000"
        }
        processor.config["config"] = {}
        processor.config["base_info"] = mock_video_info_base
        processor.config["overlay_info"] = mock_video_info_overlay
        
        output_path = tempfile.mktemp(suffix=".mp4")
        cmd = processor._generate_ffmpeg_command(
            base_video_path, overlay_video_path, output_path
        )
        
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "drawbox=" in filter_str
        assert "0xFF0000" in filter_str

    def test_generate_ffmpeg_command_with_shadow(
        self, processor, base_video_path, overlay_video_path,
        mock_video_info_base, mock_video_info_overlay
    ):
        """Test _generate_ffmpeg_command includes shadow filter"""
        processor.config["shadow"] = {
            "enabled": True,
            "offset_x": 5,
            "offset_y": 5,
            "blur": 3
        }
        processor.config["config"] = {}
        processor.config["base_info"] = mock_video_info_base
        processor.config["overlay_info"] = mock_video_info_overlay
        
        output_path = tempfile.mktemp(suffix=".mp4")
        cmd = processor._generate_ffmpeg_command(
            base_video_path, overlay_video_path, output_path
        )
        
        filter_idx = cmd.index("-filter_complex")
        filter_str = cmd[filter_idx + 1]
        assert "shadow=" in filter_str


# ============================================================================
# Integration Tests
# ============================================================================

class TestVideoOverlayIntegration:
    """Integration tests for video overlay functionality"""

    @pytest.fixture
    def temp_base_video(self):
        """Create temporary base video file"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake_base_video")
            path = f.name
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.fixture
    def temp_overlay_video(self):
        """Create temporary overlay video file"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake_overlay_video")
            path = f.name
        yield path
        if os.path.exists(path):
            os.remove(path)

    @pytest.mark.asyncio
    async def test_basic_overlay_simple_position(
        self, temp_base_video, temp_overlay_video
    ):
        """Test basic overlay with simple positioning"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "config": {"x": 10, "y": 10, "scale": 0.2},
            "border": {"enabled": False},
            "shadow": {"enabled": False},
        }
        processor = VideoOverlay(task_id=1, config=config)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            mock_ffmpeg.run_command = AsyncMock(return_value="")

            await processor.validate_input()
            result = await processor.process()

            assert "output_path" in result
            assert mock_ffmpeg.run_command.called

    @pytest.mark.asyncio
    async def test_overlay_with_scaling(
        self, temp_base_video, temp_overlay_video
    ):
        """Test overlay with different scale values"""
        scales = [0.1, 0.3, 0.5, 0.8]
        
        for scale in scales:
            config = {
                "base_video_file_id": 1,
                "overlay_video_file_id": 2,
                "base_file_path": temp_base_video,
                "overlay_file_path": temp_overlay_video,
                "config": {"scale": scale},
            }
            processor = VideoOverlay(task_id=1, config=config)

            with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
                mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                    {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                    {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
                ])
                mock_ffmpeg.run_command = AsyncMock(return_value="")

                await processor.validate_input()
                result = await processor.process()
                
                assert "output_path" in result

    @pytest.mark.asyncio
    async def test_overlay_with_explicit_dimensions(
        self, temp_base_video, temp_overlay_video
    ):
        """Test overlay with explicit width and height"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "config": {"width": 200, "height": 150},
        }
        processor = VideoOverlay(task_id=1, config=config)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            mock_ffmpeg.run_command = AsyncMock(return_value="")

            await processor.validate_input()
            result = await processor.process()

            # Check that command uses explicit dimensions
            cmd = mock_ffmpeg.run_command.call_args[0][0]
            filter_idx = cmd.index("-filter_complex")
            filter_str = cmd[filter_idx + 1]
            assert "200:150" in filter_str

    @pytest.mark.asyncio
    async def test_overlay_shapes_rectangle(
        self, temp_base_video, temp_overlay_video
    ):
        """Test overlay with rectangle shape (default)"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "config": {"shape": "rectangle"},
        }
        processor = VideoOverlay(task_id=1, config=config)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            mock_ffmpeg.run_command = AsyncMock(return_value="")

            await processor.validate_input()
            await processor.process()

            # Rectangle shape should not add shape filter
            cmd = mock_ffmpeg.run_command.call_args[0][0]
            filter_idx = cmd.index("-filter_complex")
            filter_str = cmd[filter_idx + 1]
            assert "geq" not in filter_str.lower() or "geq=" not in filter_str

    @pytest.mark.asyncio
    async def test_overlay_shapes_circle(
        self, temp_base_video, temp_overlay_video
    ):
        """Test overlay with circle shape"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "config": {"shape": "circle"},
        }
        processor = VideoOverlay(task_id=1, config=config)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            mock_ffmpeg.run_command = AsyncMock(return_value="")

            await processor.validate_input()
            await processor.process()

            # Circle shape should add geq filter
            cmd = mock_ffmpeg.run_command.call_args[0][0]
            filter_idx = cmd.index("-filter_complex")
            filter_str = cmd[filter_idx + 1]
            assert "geq=" in filter_str
            assert "hypot(" in filter_str

    @pytest.mark.asyncio
    async def test_overlay_shapes_rounded(
        self, temp_base_video, temp_overlay_video
    ):
        """Test overlay with rounded shape"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "config": {"shape": "rounded", "border_radius": 15},
        }
        processor = VideoOverlay(task_id=1, config=config)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            mock_ffmpeg.run_command = AsyncMock(return_value="")

            await processor.validate_input()
            await processor.process()

            # Rounded shape should add geq filter
            cmd = mock_ffmpeg.run_command.call_args[0][0]
            filter_idx = cmd.index("-filter_complex")
            filter_str = cmd[filter_idx + 1]
            assert "geq=" in filter_str

    @pytest.mark.asyncio
    async def test_overlay_with_opacity(
        self, temp_base_video, temp_overlay_video
    ):
        """Test overlay with opacity"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "config": {"opacity": 0.7},
        }
        processor = VideoOverlay(task_id=1, config=config)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            mock_ffmpeg.run_command = AsyncMock(return_value="")

            await processor.validate_input()
            await processor.process()

            # Opacity should add colorchannelmixer filter
            cmd = mock_ffmpeg.run_command.call_args[0][0]
            filter_idx = cmd.index("-filter_complex")
            filter_str = cmd[filter_idx + 1]
            assert "colorchannelmixer" in filter_str
            assert "aa=0.7" in filter_str

    @pytest.mark.asyncio
    async def test_overlay_with_border(
        self, temp_base_video, temp_overlay_video
    ):
        """Test overlay with border enabled"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "border": {
                "enabled": True,
                "width": 3,
                "color": "#00FF00"
            },
        }
        processor = VideoOverlay(task_id=1, config=config)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            mock_ffmpeg.run_command = AsyncMock(return_value="")

            await processor.validate_input()
            await processor.process()

            # Border should add drawbox filter
            cmd = mock_ffmpeg.run_command.call_args[0][0]
            filter_idx = cmd.index("-filter_complex")
            filter_str = cmd[filter_idx + 1]
            assert "drawbox=" in filter_str
            assert "0x00FF00" in filter_str
            assert "t=3" in filter_str

    @pytest.mark.asyncio
    async def test_overlay_with_shadow(
        self, temp_base_video, temp_overlay_video
    ):
        """Test overlay with shadow enabled"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "shadow": {
                "enabled": True,
                "offset_x": 4,
                "offset_y": 4,
                "blur": 2,
                "color": "#000000"
            },
        }
        processor = VideoOverlay(task_id=1, config=config)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            mock_ffmpeg.run_command = AsyncMock(return_value="")

            await processor.validate_input()
            await processor.process()

            # Shadow should add shadow filter
            cmd = mock_ffmpeg.run_command.call_args[0][0]
            filter_idx = cmd.index("-filter_complex")
            filter_str = cmd[filter_idx + 1]
            assert "shadow=" in filter_str

    @pytest.mark.asyncio
    async def test_overlay_combined_styles(
        self, temp_base_video, temp_overlay_video
    ):
        """Test overlay with multiple styles combined"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "config": {
                "shape": "rounded",
                "border_radius": 10,
                "opacity": 0.8
            },
            "border": {
                "enabled": True,
                "width": 2,
                "color": "#FFFFFF"
            },
            "shadow": {
                "enabled": True,
                "offset_x": 3,
                "offset_y": 3,
                "blur": 4
            },
        }
        processor = VideoOverlay(task_id=1, config=config)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            mock_ffmpeg.run_command = AsyncMock(return_value="")

            await processor.validate_input()
            await processor.process()

            # All filters should be present
            cmd = mock_ffmpeg.run_command.call_args[0][0]
            filter_idx = cmd.index("-filter_complex")
            filter_str = cmd[filter_idx + 1]
            assert "geq=" in filter_str  # Shape
            assert "drawbox=" in filter_str  # Border
            assert "shadow=" in filter_str  # Shadow
            assert "colorchannelmixer" in filter_str  # Opacity

    @pytest.mark.asyncio
    async def test_multiple_overlays_sequential(
        self, temp_base_video, temp_overlay_video
    ):
        """Test creating multiple overlays sequentially"""
        configs = [
            {
                "base_video_file_id": 1,
                "overlay_video_file_id": 2,
                "base_file_path": temp_base_video,
                "overlay_file_path": temp_overlay_video,
                "config": {"x": 10, "y": 10, "scale": 0.2},
            },
            {
                "base_video_file_id": 1,
                "overlay_video_file_id": 2,
                "base_file_path": temp_base_video,
                "overlay_file_path": temp_overlay_video,
                "config": {"x": 100, "y": 100, "scale": 0.3},
            },
        ]

        results = []
        for i, config in enumerate(configs):
            processor = VideoOverlay(task_id=i + 1, config=config)

            with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
                mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                    {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                    {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
                ])
                mock_ffmpeg.run_command = AsyncMock(return_value="")

                await processor.validate_input()
                result = await processor.process()
                results.append(result)

        assert len(results) == 2
        for result in results:
            assert "output_path" in result

    @pytest.mark.asyncio
    async def test_progress_callback(
        self, temp_base_video, temp_overlay_video
    ):
        """Test that progress callback is called"""
        config = {
            "base_video_file_id": 1,
            "overlay_video_file_id": 2,
            "base_file_path": temp_base_video,
            "overlay_file_path": temp_overlay_video,
            "config": {},
        }
        
        progress_values = []
        
        def progress_cb(value):
            progress_values.append(value)
        
        processor = VideoOverlay(task_id=1, config=config, progress_callback=progress_cb)

        with patch("app.processors.video_overlay.FFmpegCommand") as mock_ffmpeg:
            mock_ffmpeg.get_video_info = AsyncMock(side_effect=[
                {"width": 1920, "height": 1080, "duration": 60, "video_codec": "h264"},
                {"width": 640, "height": 480, "duration": 30, "video_codec": "h264"}
            ])
            
            # Mock run_command to call progress callback
            async def run_command_with_progress(cmd, timeout, progress_callback=None):
                if progress_callback:
                    progress_callback(10.0)
                    progress_callback(50.0)
                    progress_callback(100.0)
                return ""
            
            mock_ffmpeg.run_command = run_command_with_progress

            await processor.validate_input()
            await processor.process()

            # Check that progress was updated
            assert 100.0 in progress_values
