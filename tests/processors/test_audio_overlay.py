"""
Unit tests for AudioOverlay processor
"""
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

# Import schemas directly to avoid circular dependency
from app.schemas.audio_overlay import AudioOverlayMode, AudioOverlayRequest
from app.processors.audio_overlay import AudioOverlay
from app.ffmpeg.exceptions import FFmpegValidationError


# Unit tests for schemas
class TestAudioOverlaySchemas:
    """Тесты для Pydantic schemas наложения аудио"""

    def test_audio_overlay_mode_enum(self):
        """Тест перечисления AudioOverlayMode"""
        assert AudioOverlayMode.REPLACE == "replace"
        assert AudioOverlayMode.MIX == "mix"

    def test_audio_overlay_request_minimal(self):
        """Тест AudioOverlayRequest с минимальными полями"""
        request = AudioOverlayRequest(
            video_file_id=1,
            audio_file_id=2
        )
        assert request.video_file_id == 1
        assert request.audio_file_id == 2
        assert request.mode.value == "replace"
        assert request.offset == 0.0
        assert request.duration is None
        assert request.original_volume == 1.0
        assert request.overlay_volume == 1.0
        assert request.output_filename is None

    def test_audio_overlay_request_full(self):
        """Тест AudioOverlayRequest со всеми полями"""
        request = AudioOverlayRequest(
            video_file_id=1,
            audio_file_id=2,
            mode=AudioOverlayMode.MIX,
            offset=5.0,
            duration=10.0,
            original_volume=0.8,
            overlay_volume=1.2,
            output_filename="output.mp4"
        )
        assert request.video_file_id == 1
        assert request.audio_file_id == 2
        assert request.mode == AudioOverlayMode.MIX
        assert request.offset == 5.0
        assert request.duration == 10.0
        assert request.original_volume == 0.8
        assert request.overlay_volume == 1.2
        assert request.output_filename == "output.mp4"

    def test_audio_overlay_request_invalid_file_id(self):
        """Тест AudioOverlayRequest с некорректным file_id"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            AudioOverlayRequest(video_file_id=-1, audio_file_id=2)
        assert "greater than 0" in str(exc_info.value)

    def test_audio_overlay_request_invalid_offset(self):
        """Тест AudioOverlayRequest с некорректным offset"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            AudioOverlayRequest(video_file_id=1, audio_file_id=2, offset=-1.0)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_audio_overlay_request_invalid_duration(self):
        """Тест AudioOverlayRequest с некорректным duration"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            AudioOverlayRequest(video_file_id=1, audio_file_id=2, duration=-1.0)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_audio_overlay_request_invalid_original_volume_low(self):
        """Тест AudioOverlayRequest с некорректной громкостью (меньше 0)"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            AudioOverlayRequest(video_file_id=1, audio_file_id=2, original_volume=-0.1)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_audio_overlay_request_invalid_original_volume_high(self):
        """Тест AudioOverlayRequest с некорректной громкостью (больше 2)"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            AudioOverlayRequest(video_file_id=1, audio_file_id=2, original_volume=2.1)
        assert "less than or equal to 2" in str(exc_info.value)

    def test_audio_overlay_request_invalid_overlay_volume(self):
        """Тест AudioOverlayRequest с некорректной громкостью наложения"""
        from pydantic import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            AudioOverlayRequest(video_file_id=1, audio_file_id=2, overlay_volume=3.0)
        assert "less than or equal to 2" in str(exc_info.value)

    def test_audio_overlay_request_model_dump(self):
        """Тест преобразования AudioOverlayRequest в словарь"""
        request = AudioOverlayRequest(
            video_file_id=1,
            audio_file_id=2,
            mode=AudioOverlayMode.MIX,
            offset=5.0,
            duration=10.0,
            original_volume=0.8,
            overlay_volume=1.2,
            output_filename="output.mp4"
        )
        data = request.model_dump()

        assert data["video_file_id"] == 1
        assert data["audio_file_id"] == 2
        assert data["mode"] == AudioOverlayMode.MIX
        assert data["offset"] == 5.0
        assert data["duration"] == 10.0
        assert data["original_volume"] == 0.8
        assert data["overlay_volume"] == 1.2
        assert data["output_filename"] == "output.mp4"


# Unit tests for AudioOverlay validation
class TestAudioOverlayValidation:
    """Тесты валидации AudioOverlay"""

    @pytest.fixture
    def processor(self):
        """Создание экземпляра процессора"""
        return AudioOverlay(
            task_id=1,
            config={
                "video_path": "/tmp/video.mp4",
                "audio_path": "/tmp/audio.mp3",
                "mode": "replace"
            },
            progress_callback=None
        )

    @pytest.mark.asyncio
    async def test_validate_input_success(self, processor):
        """Тест успешной валидации"""
        with patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_video, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_audio_info") as mock_audio:
            mock_video.return_value = {"duration": 60.0}
            mock_audio.return_value = {"duration": 30.0}

            await processor.validate_input()

            mock_video.assert_called_once_with("/tmp/video.mp4")
            mock_audio.assert_called_once_with("/tmp/audio.mp3")

    @pytest.mark.asyncio
    async def test_validate_input_missing_video_path(self, processor):
        """Тест валидации без video_path"""
        processor.config["video_path"] = None

        with pytest.raises(FFmpegValidationError) as exc_info:
            await processor.validate_input()
        assert "video file path is required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_input_missing_audio_path(self, processor):
        """Тест валидации без audio_path"""
        processor.config["audio_path"] = None

        with pytest.raises(FFmpegValidationError) as exc_info:
            await processor.validate_input()
        assert "audio file path is required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_input_invalid_video(self, processor):
        """Тест валидации с некорректным видео файлом"""
        with patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_video:
            mock_video.side_effect = Exception("Invalid video")

            with pytest.raises(FFmpegValidationError) as exc_info:
                await processor.validate_input()
            assert "video file is invalid or corrupted" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_input_invalid_audio(self, processor):
        """Тест валидации с некорректным аудио файлом"""
        with patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_video, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_audio_info") as mock_audio:
            mock_video.return_value = {"duration": 60.0}
            mock_audio.side_effect = Exception("Invalid audio")

            with pytest.raises(FFmpegValidationError) as exc_info:
                await processor.validate_input()
            assert "audio file is invalid or corrupted" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_input_duration_exceeds_audio(self, processor):
        """Тест валидации с duration превышающим длину аудио"""
        processor.config["duration"] = 60.0

        with patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_video, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_audio_info") as mock_audio:
            mock_video.return_value = {"duration": 60.0}
            mock_audio.return_value = {"duration": 30.0}

            with pytest.raises(FFmpegValidationError) as exc_info:
                await processor.validate_input()
            assert "exceeds audio length" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_input_offset_exceeds_audio(self, processor):
        """Тест валидации с offset превышающим длину аудио"""
        processor.config["offset"] = 40.0

        with patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_video, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_audio_info") as mock_audio:
            mock_video.return_value = {"duration": 60.0}
            mock_audio.return_value = {"duration": 30.0}

            with pytest.raises(FFmpegValidationError) as exc_info:
                await processor.validate_input()
            assert "offset" in str(exc_info.value).lower() and "exceeds audio length" in str(exc_info.value).lower()


# Unit tests for AudioOverlay command generation
class TestAudioOverlayCommandGeneration:
    """Тесты генерации команд FFmpeg"""

    @pytest.fixture
    def processor(self):
        """Создание экземпляра процессора"""
        return AudioOverlay(
            task_id=1,
            config={
                "video_path": "/tmp/video.mp4",
                "audio_path": "/tmp/audio.mp3",
                "mode": "replace",
                "offset": 0.0,
                "duration": None,
                "original_volume": 1.0,
                "overlay_volume": 1.0
            },
            progress_callback=None
        )

    def test_generate_ffmpeg_command_replace(self, processor):
        """Тест генерации команды для replace режима"""
        cmd = processor._generate_ffmpeg_command_replace(
            "/tmp/video.mp4",
            "/tmp/audio.mp3",
            "/tmp/output.mp4"
        )

        assert "ffmpeg" in cmd[0]
        assert "-y" in cmd
        assert "-i" in cmd
        assert "/tmp/video.mp4" in cmd
        assert "/tmp/audio.mp3" in cmd
        assert "-map" in cmd
        assert "0:v:0" in cmd
        assert "1:a:0" in cmd
        assert "-c:v" in cmd
        assert "copy" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert "-shortest" in cmd
        assert "/tmp/output.mp4" in cmd

    def test_generate_ffmpeg_command_mix(self, processor):
        """Тест генерации команды для mix режима"""
        cmd = processor._generate_ffmpeg_command_mix(
            "/tmp/video.mp4",
            "/tmp/audio.mp3",
            "/tmp/output.mp4"
        )

        assert "ffmpeg" in cmd[0]
        assert "-y" in cmd
        assert "-i" in cmd
        assert "/tmp/video.mp4" in cmd
        assert "/tmp/audio.mp3" in cmd
        assert "-ss" in cmd
        assert "-filter_complex" in cmd
        # Check for volume in filter complex (with =)
        filter_complex = None
        for i, arg in enumerate(cmd):
            if arg == "-filter_complex" and i + 1 < len(cmd):
                filter_complex = cmd[i + 1]
                break
        assert filter_complex is not None
        assert "volume=1.0" in filter_complex
        assert "amix=" in filter_complex
        assert "-c:v" in cmd
        assert "copy" in cmd
        assert "-c:a" in cmd
        assert "aac" in cmd
        assert "/tmp/output.mp4" in cmd

    def test_generate_ffmpeg_command_mix_with_duration(self, processor):
        """Тест генерации команды для mix режима с duration"""
        processor.config["duration"] = 10.0
        cmd = processor._generate_ffmpeg_command_mix(
            "/tmp/video.mp4",
            "/tmp/audio.mp3",
            "/tmp/output.mp4"
        )

        assert "-t" in cmd
        assert "10.0" in cmd

    def test_generate_ffmpeg_command_mix_with_volume(self, processor):
        """Тест генерации команды для mix режима с настройками громкости"""
        processor.config["original_volume"] = 0.8
        processor.config["overlay_volume"] = 1.2
        cmd = processor._generate_ffmpeg_command_mix(
            "/tmp/video.mp4",
            "/tmp/audio.mp3",
            "/tmp/output.mp4"
        )

        filter_complex = None
        for i, arg in enumerate(cmd):
            if arg == "-filter_complex" and i + 1 < len(cmd):
                filter_complex = cmd[i + 1]
                break

        assert filter_complex is not None
        assert "volume=0.8" in filter_complex
        assert "volume=1.2" in filter_complex

    def test_generate_ffmpeg_command_mix_with_offset(self, processor):
        """Тест генерации команды для mix режима с offset"""
        processor.config["offset"] = 5.0
        cmd = processor._generate_ffmpeg_command_mix(
            "/tmp/video.mp4",
            "/tmp/audio.mp3",
            "/tmp/output.mp4"
        )

        # Проверяем, что offset применяется к аудио
        offset_index = cmd.index("-ss")
        assert cmd[offset_index + 1] == "5.0"


# Unit tests for AudioOverlay processing
class TestAudioOverlayProcess:
    """Тесты обработки аудио"""

    @pytest.fixture
    def processor(self):
        """Создание экземпляра процессора"""
        processor = AudioOverlay(
            task_id=1,
            config={
                "video_path": "/tmp/video.mp4",
                "audio_path": "/tmp/audio.mp3",
                "mode": "replace",
                "timeout": 3600
            },
            progress_callback=None
        )
        return processor

    @pytest.mark.asyncio
    async def test_process_replace(self, processor):
        """Тест обработки в режиме replace"""
        progress_values = []
        
        def capture_progress(p):
            progress_values.append(p)
        
        processor.progress_callback = capture_progress
        
        with patch("app.processors.audio_overlay.FFmpegCommand.run_command") as mock_run, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_info:
            mock_info.return_value = {"duration": 60.0}
            mock_run.return_value = ""

            result = await processor.process_replace()

            assert "output_path" in result
            mock_run.assert_called_once()
            assert 100.0 in progress_values

    @pytest.mark.asyncio
    async def test_process_mix(self, processor):
        """Тест обработки в режиме mix"""
        processor.config["mode"] = "mix"
        
        progress_values = []
        
        def capture_progress(p):
            progress_values.append(p)
        
        processor.progress_callback = capture_progress

        with patch("app.processors.audio_overlay.FFmpegCommand.run_command") as mock_run, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_info:
            mock_info.return_value = {"duration": 60.0}
            mock_run.return_value = ""

            result = await processor.process_mix()

            assert "output_path" in result
            mock_run.assert_called_once()
            assert 100.0 in progress_values

    @pytest.mark.asyncio
    async def test_process_replace_with_custom_output(self, processor):
        """Тест обработки с указанным выходным файлом"""
        processor.config["output_path"] = "/tmp/custom_output.mp4"

        with patch("app.processors.audio_overlay.FFmpegCommand.run_command") as mock_run, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_info:
            mock_info.return_value = {"duration": 60.0}
            mock_run.return_value = ""

            result = await processor.process_replace()

            assert result["output_path"] == "/tmp/custom_output.mp4"

    @pytest.mark.asyncio
    async def test_process_with_progress_callback(self, processor):
        """Тест обработки с callback прогресса"""
        progress_values = []

        def progress_cb(p):
            progress_values.append(p)

        processor.progress_callback = progress_cb

        with patch("app.processors.audio_overlay.FFmpegCommand.run_command") as mock_run, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_info:
            mock_info.return_value = {"duration": 60.0}
            mock_run.return_value = ""

            await processor.process_replace()

            assert 100.0 in progress_values

    @pytest.mark.asyncio
    async def test_process_replace_mode(self, processor):
        """Тест основной обработки в режиме replace"""
        with patch.object(processor, 'process_replace', new_callable=AsyncMock) as mock_replace:
            mock_replace.return_value = {"output_path": "/tmp/output.mp4"}

            result = await processor.process()

            assert result["output_path"] == "/tmp/output.mp4"
            mock_replace.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_mix_mode(self, processor):
        """Тест основной обработки в режиме mix"""
        processor.config["mode"] = "mix"

        with patch.object(processor, 'process_mix', new_callable=AsyncMock) as mock_mix:
            mock_mix.return_value = {"output_path": "/tmp/output.mp4"}

            result = await processor.process()

            assert result["output_path"] == "/tmp/output.mp4"
            mock_mix.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_invalid_mode(self, processor):
        """Тест обработки с некорректным режимом"""
        processor.config["mode"] = "invalid"

        with pytest.raises(FFmpegValidationError) as exc_info:
            await processor.process()
        assert "unknown mode" in str(exc_info.value).lower()


# Integration tests
class TestAudioOverlayIntegration:
    """Интеграционные тесты для AudioOverlay"""

    @pytest.mark.asyncio
    async def test_full_replace_workflow(self):
        """Тест полного workflow для replace режима"""
        processor = AudioOverlay(
            task_id=1,
            config={
                "video_path": "/tmp/video.mp4",
                "audio_path": "/tmp/audio.mp3",
                "mode": "replace",
                "timeout": 3600
            },
            progress_callback=None
        )

        with patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_video_info, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_audio_info") as mock_audio_info, \
             patch("app.processors.audio_overlay.FFmpegCommand.run_command") as mock_run:
            mock_video_info.return_value = {"duration": 60.0}
            mock_audio_info.return_value = {"duration": 30.0}
            mock_run.return_value = ""

            result = await processor.run()

            assert "output_path" in result
            # get_video_info is called in validate_input AND in process_replace
            assert mock_video_info.call_count >= 1
            mock_audio_info.assert_called_once()
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_mix_workflow(self):
        """Тест полного workflow для mix режима"""
        processor = AudioOverlay(
            task_id=1,
            config={
                "video_path": "/tmp/video.mp4",
                "audio_path": "/tmp/audio.mp3",
                "mode": "mix",
                "offset": 2.0,
                "original_volume": 0.9,
                "overlay_volume": 1.1,
                "timeout": 3600
            },
            progress_callback=None
        )

        with patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_video_info, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_audio_info") as mock_audio_info, \
             patch("app.processors.audio_overlay.FFmpegCommand.run_command") as mock_run:
            mock_video_info.return_value = {"duration": 60.0}
            mock_audio_info.return_value = {"duration": 30.0}
            mock_run.return_value = ""

            result = await processor.run()

            assert "output_path" in result

            # Проверка команды
            call_args = mock_run.call_args[0][0]
            assert "-filter_complex" in call_args
            assert "-ss" in call_args

    @pytest.mark.asyncio
    async def test_workflow_with_duration(self):
        """Тест workflow с duration"""
        processor = AudioOverlay(
            task_id=1,
            config={
                "video_path": "/tmp/video.mp4",
                "audio_path": "/tmp/audio.mp3",
                "mode": "mix",
                "duration": 15.0,
                "timeout": 3600
            },
            progress_callback=None
        )

        with patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_video_info, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_audio_info") as mock_audio_info, \
             patch("app.processors.audio_overlay.FFmpegCommand.run_command") as mock_run:
            mock_video_info.return_value = {"duration": 60.0}
            mock_audio_info.return_value = {"duration": 30.0}
            mock_run.return_value = ""

            await processor.run()

            # Проверка, что duration передан в команду
            call_args = mock_run.call_args[0][0]
            assert "-t" in call_args
            assert "15.0" in call_args

    @pytest.mark.asyncio
    async def test_workflow_cleanup(self):
        """Тест очистки временных файлов"""
        processor = AudioOverlay(
            task_id=1,
            config={
                "video_path": "/tmp/video.mp4",
                "audio_path": "/tmp/audio.mp3",
                "mode": "replace",
                "timeout": 3600
            },
            progress_callback=None
        )

        # Добавляем временный файл
        processor.add_temp_file("/tmp/temp_file.mp4")

        with patch("app.processors.audio_overlay.FFmpegCommand.get_video_info") as mock_video_info, \
             patch("app.processors.audio_overlay.FFmpegCommand.get_audio_info") as mock_audio_info, \
             patch("app.processors.audio_overlay.FFmpegCommand.run_command") as mock_run:
            mock_video_info.return_value = {"duration": 60.0}
            mock_audio_info.return_value = {"duration": 30.0}
            mock_run.return_value = ""

            with patch("os.path.exists", return_value=True), \
                 patch("os.remove") as mock_remove:
                await processor.run()

                # Проверка, что временный файл был удален
                assert any("/tmp/temp_file.mp4" in str(call) for call in mock_remove.call_args_list)


# Helper fixtures
@pytest.fixture
def mock_processor():
    """Мок для AudioOverlay"""
    processor = AudioOverlay(
        task_id=1,
        config={
            "video_path": "/tmp/video.mp4",
            "audio_path": "/tmp/audio.mp3",
            "mode": "replace"
        },
        progress_callback=None
    )
    # Добавляем список для хранения значений прогресса
    processor.progress_values = []
    original_update = processor.update_progress
    def capture_progress(p):
        processor.progress_values.append(p)
        original_update(p)
    processor.update_progress = capture_progress
    return processor
