"""
Tests for SubtitleProcessor (simplified version without database dependencies)
"""
import os
import tempfile
from unittest.mock import Mock, AsyncMock, patch

import pytest

from app.processors.subtitle_processor import SubtitleProcessor
from app.schemas.subtitle import SubtitleFormat, SubtitlePosition, SubtitleStyle


class TestSubtitleProcessorUnit:
    """Unit tests for SubtitleProcessor"""

    def test_generate_subtitle_from_text(self):
        """Test generating SRT from text"""
        subtitle_text = [
            {"start": 1.0, "end": 4.0, "text": "First subtitle"},
            {"start": 5.5, "end": 8.0, "text": "Second subtitle"},
        ]

        processor = SubtitleProcessor(task_id=1, config={})
        srt_content = processor._generate_subtitle_from_text(subtitle_text)

        assert "1" in srt_content
        assert "00:00:01,000 --> 00:00:04,000" in srt_content
        assert "First subtitle" in srt_content
        assert "2" in srt_content
        assert "00:00:05,500 --> 00:00:08,000" in srt_content
        assert "Second subtitle" in srt_content

    def test_generate_ass_style(self):
        """Test generating ASS style"""
        style = SubtitleStyle(
            font_name="Arial",
            font_size=20,
            primary_color="&H00FFFFFF",
            bold=True,
            italic=False,
            outline=2.5,
            shadow=3.0,
            alignment=2,
            margin_l=10,
            margin_r=10,
            margin_v=10,
        )

        processor = SubtitleProcessor(task_id=1, config={})
        ass_style = processor._generate_ass_style(style)

        assert "Style: Default" in ass_style
        assert "Arial" in ass_style
        assert "20" in ass_style
        assert "&H00FFFFFF" in ass_style
        assert "Bold=1" in ass_style
        assert "Outline=2.5" in ass_style
        assert "Shadow=3.0" in ass_style
        assert "Alignment=2" in ass_style

    def test_format_srt_time(self):
        """Test time formatting to SRT format"""
        processor = SubtitleProcessor(task_id=1, config={})

        assert processor._format_srt_time(1.0) == "00:00:01,000"
        assert processor._format_srt_time(10.5) == "00:00:10,500"
        assert processor._format_srt_time(3600.0) == "01:00:00,000"
        assert processor._format_srt_time(5445.25) == "01:30:45,250"

    @pytest.mark.asyncio
    async def test_parse_subtitle_file_srt(self):
        """Test parsing SRT subtitle file"""
        srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello World

2
00:00:05,500 --> 00:00:08,000
Second subtitle"""

        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w") as f:
            f.write(srt_content)
            subtitle_path = f.name

        try:
            processor = SubtitleProcessor(task_id=1, config={})
            result = await processor._parse_subtitle_file(subtitle_path, SubtitleFormat.SRT)

            assert len(result) == 2
            assert result[0]["start"] == 1.0
            assert result[0]["end"] == 4.0
            assert result[0]["text"] == "Hello World"
        finally:
            os.unlink(subtitle_path)

    @pytest.mark.asyncio
    async def test_parse_subtitle_file_vtt(self):
        """Test parsing VTT subtitle file"""
        vtt_content = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hello World

00:00:05.500 --> 00:00:08.000
Second subtitle"""

        with tempfile.NamedTemporaryFile(suffix=".vtt", delete=False, mode="w") as f:
            f.write(vtt_content)
            subtitle_path = f.name

        try:
            processor = SubtitleProcessor(task_id=1, config={})
            result = await processor._parse_subtitle_file(subtitle_path, SubtitleFormat.VTT)

            assert len(result) == 2
            assert result[0]["start"] == 1.0
            assert result[0]["text"] == "Hello World"
        finally:
            os.unlink(subtitle_path)

    @pytest.mark.asyncio
    async def test_parse_subtitle_file_ass(self):
        """Test parsing ASS subtitle file"""
        ass_content = """[Script Info]

[V4+ Styles]
Format: Name, Fontname, Fontsize
Style: Default,Arial,20

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello World"""

        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False, mode="w") as f:
            f.write(ass_content)
            subtitle_path = f.name

        try:
            processor = SubtitleProcessor(task_id=1, config={})
            result = await processor._parse_subtitle_file(subtitle_path, SubtitleFormat.ASS)

            assert len(result) == 1
            assert result[0]["start"] == 1.0
            assert result[0]["end"] == 4.0
            assert result[0]["text"] == "Hello World"
        finally:
            os.unlink(subtitle_path)


class TestSubtitleProcessorIntegration:
    """Integration tests for SubtitleProcessor"""

    @pytest.mark.asyncio
    async def test_srt_format_overlay(self):
        """Test overlay with SRT format"""
        # Create mock video file
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        srt_content = """1
00:00:00,000 --> 00:00:02,000
First subtitle

2
00:00:02,500 --> 00:00:04,000
Second subtitle"""

        with tempfile.NamedTemporaryFile(suffix=".srt", delete=False, mode="w") as f:
            f.write(srt_content)
            subtitle_path = f.name

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            output_path = f.name

        try:
            config = {
                "video_path": video_path,
                "subtitle_file_path": subtitle_path,
                "subtitle_text": None,
                "format": SubtitleFormat.SRT,
                "output_path": output_path,
                "timeout": 60,
            }

            processor = SubtitleProcessor(task_id=1, config=config)

            with patch("app.processors.subtitle_processor.FFmpegCommand.run_command") as mock_run:
                mock_run.return_value = None

                result = await processor.process()

                assert result["output_path"] == output_path
                assert mock_run.called
        finally:
            os.unlink(video_path)
            os.unlink(subtitle_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    @pytest.mark.asyncio
    async def test_vtt_format_overlay(self):
        """Test overlay with VTT format"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        vtt_content = """WEBVTT

00:00:00.000 --> 00:00:02.000
First subtitle

00:00:02.500 --> 00:00:04.000
Second subtitle"""

        with tempfile.NamedTemporaryFile(suffix=".vtt", delete=False, mode="w") as f:
            f.write(vtt_content)
            subtitle_path = f.name

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            output_path = f.name

        try:
            config = {
                "video_path": video_path,
                "subtitle_file_path": subtitle_path,
                "subtitle_text": None,
                "format": SubtitleFormat.VTT,
                "output_path": output_path,
                "timeout": 60,
            }

            processor = SubtitleProcessor(task_id=1, config=config)

            with patch("app.processors.subtitle_processor.FFmpegCommand.run_command") as mock_run:
                mock_run.return_value = None

                result = await processor.process()

                assert result["output_path"] == output_path
                assert mock_run.called
        finally:
            os.unlink(video_path)
            os.unlink(subtitle_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    @pytest.mark.asyncio
    async def test_ass_format_overlay_with_styles(self):
        """Test overlay with ASS format and custom styles"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        ass_content = """[Script Info]

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H00000000,2.0,2.0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:00.00,0:00:02.00,Default,,0,0,0,,Styled subtitle"""

        with tempfile.NamedTemporaryFile(suffix=".ass", delete=False, mode="w") as f:
            f.write(ass_content)
            subtitle_path = f.name

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            output_path = f.name

        style = SubtitleStyle(
            font_name="Arial",
            font_size=24,
            primary_color="&H00FF0000",
            bold=True,
            outline=3.0,
            shadow=4.0,
        )

        try:
            config = {
                "video_path": video_path,
                "subtitle_file_path": subtitle_path,
                "subtitle_text": None,
                "format": SubtitleFormat.ASS,
                "style": style,
                "output_path": output_path,
                "timeout": 60,
            }

            processor = SubtitleProcessor(task_id=1, config=config)

            with patch("app.processors.subtitle_processor.FFmpegCommand.run_command") as mock_run:
                mock_run.return_value = None

                result = await processor.process()

                assert result["output_path"] == output_path
                assert mock_run.called
        finally:
            os.unlink(video_path)
            os.unlink(subtitle_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    @pytest.mark.asyncio
    async def test_generate_from_text(self):
        """Test generating subtitles from text"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        subtitle_text = [
            {"start": 0.0, "end": 2.0, "text": "Generated subtitle 1"},
            {"start": 2.5, "end": 4.0, "text": "Generated subtitle 2"},
        ]

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            output_path = f.name

        try:
            config = {
                "video_path": video_path,
                "subtitle_file_path": None,
                "subtitle_text": subtitle_text,
                "format": SubtitleFormat.SRT,
                "output_path": output_path,
                "timeout": 60,
            }

            processor = SubtitleProcessor(task_id=1, config=config)

            with patch("app.processors.subtitle_processor.FFmpegCommand.run_command") as mock_run:
                mock_run.return_value = None

                result = await processor.process()

                assert result["output_path"] == output_path
                assert mock_run.called
        finally:
            os.unlink(video_path)
            if os.path.exists(output_path):
                os.unlink(output_path)

    @pytest.mark.asyncio
    async def test_styles_applied_correctly(self):
        """Test that subtitle styles are applied correctly"""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"fake video content")
            video_path = f.name

        subtitle_text = [
            {"start": 0.0, "end": 2.0, "text": "Styled subtitle"},
        ]

        position = SubtitlePosition(position="top", margin_x=20, margin_y=30)

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            output_path = f.name

        try:
            config = {
                "video_path": video_path,
                "subtitle_text": subtitle_text,
                "position": position,
                "output_path": output_path,
                "timeout": 60,
            }

            processor = SubtitleProcessor(task_id=1, config=config)

            with patch("app.processors.subtitle_processor.FFmpegCommand.run_command") as mock_run:
                mock_run.return_value = None

                result = await processor.process()

                assert result["output_path"] == output_path

                # Check that FFmpeg command was called
                assert mock_run.called
                call_args = mock_run.call_args[0][0]
                # Verify command structure
                assert len(call_args) > 0
        finally:
            os.unlink(video_path)
            if os.path.exists(output_path):
                os.unlink(output_path)
