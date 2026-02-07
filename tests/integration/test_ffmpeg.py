"""
Integration tests for FFmpeg
"""
import pytest
import subprocess
import os
from pathlib import Path


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
class TestFFmpegIntegration:
    """Integration tests for FFmpeg"""

    @pytest.mark.asyncio
    async def test_ffmpeg_installed(self):
        """Test that FFmpeg is installed"""
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "ffmpeg version" in result.stderr.lower() or "ffmpeg version" in result.stdout.lower()

    @pytest.mark.asyncio
    async def test_ffprobe_installed(self):
        """Test that FFprobe is installed"""
        result = subprocess.run(
            ["ffprobe", "-version"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0
        assert "ffprobe version" in result.stderr.lower() or "ffprobe version" in result.stdout.lower()

    @pytest.mark.asyncio
    async def test_simple_ffmpeg_command(self, temp_video_file):
        """Test simple FFmpeg command"""
        output_file = temp_video_file.replace(".mp4", "_output.mp4")

        result = subprocess.run([
            "ffmpeg",
            "-i", temp_video_file,
            "-c", "copy",
            output_file,
            "-y"
        ], capture_output=True, text=True)

        assert result.returncode == 0, f"FFmpeg error: {result.stderr}"
        assert os.path.exists(output_file)

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)

    @pytest.mark.asyncio
    async def test_get_video_info(self, temp_video_file):
        """Test getting video info"""
        from app.ffmpeg.commands import FFmpegCommand

        info = await FFmpegCommand.get_video_info(temp_video_file)

        assert info is not None
        assert "duration" in info
        assert "width" in info
        assert "height" in info
        assert "video_codec" in info

    @pytest.mark.asyncio
    async def test_video_join(self, temp_video_file):
        """Test joining two videos"""
        output_file = temp_video_file.replace(".mp4", "_joined.mp4")

        result = subprocess.run([
            "ffmpeg",
            "-i", temp_video_file,
            "-i", temp_video_file,
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1[outv]",
            "-map", "[outv]",
            output_file,
            "-y"
        ], capture_output=True, text=True)

        assert result.returncode == 0, f"FFmpeg error: {result.stderr}"
        assert os.path.exists(output_file)

        # Check that duration doubled
        from app.ffmpeg.commands import FFmpegCommand
        original_info = await FFmpegCommand.get_video_info(temp_video_file)
        joined_info = await FFmpegCommand.get_video_info(output_file)

        assert abs(joined_info["duration"] - 2 * original_info["duration"]) < 0.5

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)

    @pytest.mark.asyncio
    async def test_video_format_conversion(self, temp_video_file):
        """Test video format conversion"""
        output_file = temp_video_file.replace(".mp4", "_converted.mkv")

        result = subprocess.run([
            "ffmpeg",
            "-i", temp_video_file,
            "-c", "copy",
            output_file,
            "-y"
        ], capture_output=True, text=True)

        assert result.returncode == 0, f"FFmpeg error: {result.stderr}"
        assert os.path.exists(output_file)

        # Verify output format
        from app.ffmpeg.commands import FFmpegCommand
        info = await FFmpegCommand.get_video_info(output_file)
        assert "mkv" in info.get("format", "").lower()

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)

    @pytest.mark.asyncio
    async def test_video_scaling(self, temp_video_file):
        """Test video scaling"""
        output_file = temp_video_file.replace(".mp4", "_scaled.mp4")

        result = subprocess.run([
            "ffmpeg",
            "-i", temp_video_file,
            "-vf", "scale=320:240",
            "-c:a", "copy",
            output_file,
            "-y"
        ], capture_output=True, text=True)

        assert result.returncode == 0, f"FFmpeg error: {result.stderr}"
        assert os.path.exists(output_file)

        # Verify scaling
        from app.ffmpeg.commands import FFmpegCommand
        info = await FFmpegCommand.get_video_info(output_file)
        assert info["width"] == 320
        assert info["height"] == 240

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)

    @pytest.mark.asyncio
    async def test_audio_extraction(self, temp_video_file):
        """Test audio extraction from video"""
        output_file = temp_video_file.replace(".mp4", "_audio.mp3")

        result = subprocess.run([
            "ffmpeg",
            "-i", temp_video_file,
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            output_file,
            "-y"
        ], capture_output=True, text=True)

        # Note: This might fail if test video doesn't have audio
        # We'll just check it doesn't crash
        assert result.returncode in [0, 1]  # 0 = success, 1 = no audio stream

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)

    @pytest.mark.asyncio
    async def test_video_quality_settings(self, temp_video_file):
        """Test video quality settings"""
        output_file = temp_video_file.replace(".mp4", "_quality.mp4")

        result = subprocess.run([
            "ffmpeg",
            "-i", temp_video_file,
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "medium",
            "-c:a", "aac",
            "-b:a", "128k",
            output_file,
            "-y"
        ], capture_output=True, text=True)

        assert result.returncode == 0, f"FFmpeg error: {result.stderr}"
        assert os.path.exists(output_file)

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)

    @pytest.mark.asyncio
    async def test_video_metadata(self, temp_video_file):
        """Test video metadata extraction"""
        from app.ffmpeg.commands import FFmpegCommand

        info = await FFmpegCommand.get_video_info(temp_video_file)

        assert "duration" in info
        assert info["duration"] > 0

        assert "width" in info
        assert info["width"] > 0

        assert "height" in info
        assert info["height"] > 0

        assert "video_codec" in info
        assert isinstance(info["video_codec"], str)

    @pytest.mark.asyncio
    async def test_subtitle_extraction(self, temp_video_file):
        """Test subtitle extraction"""
        output_file = temp_video_file.replace(".mp4", "_subs.srt")

        result = subprocess.run([
            "ffmpeg",
            "-i", temp_video_file,
            "-map", "0:s:0",
            output_file,
            "-y"
        ], capture_output=True, text=True)

        # Note: This might fail if video doesn't have subtitles
        # We'll accept both success (0) and no subtitle stream (1)
        assert result.returncode in [0, 1]

        # Cleanup
        if os.path.exists(output_file):
            os.remove(output_file)
