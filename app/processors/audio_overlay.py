"""
Audio overlay processor: replace or mix audio tracks in video files
"""
from typing import Any, Dict, List

from app.ffmpeg.commands import FFmpegCommand
from app.ffmpeg.exceptions import FFmpegValidationError
from app.processors.base_processor import BaseProcessor
from app.utils.temp_files import create_temp_file


class AudioOverlay(BaseProcessor):
    """Наложение аудио на видео: замена или смешивание с оригиналом."""

    async def validate_input(self) -> None:
        """
        Проверка входных данных.

        Raises:
            FFmpegValidationError: Если файлы не найдены или некорректны
        """
        video_path = self.config.get("video_path")
        audio_path = self.config.get("audio_path")

        if not video_path:
            raise FFmpegValidationError("Video file path is required")
        if not audio_path:
            raise FFmpegValidationError("Audio file path is required")

        # Проверка существования видео файла
        try:
            await FFmpegCommand.get_video_info(video_path)
        except Exception as e:
            raise FFmpegValidationError(f"Video file is invalid or corrupted: {e}")

        # Проверка существования аудио файла
        try:
            audio_info = await FFmpegCommand.get_audio_info(audio_path)
        except Exception as e:
            raise FFmpegValidationError(f"Audio file is invalid or corrupted: {e}")

        # Проверка длительности аудио
        offset = self.config.get("offset", 0.0)
        duration = self.config.get("duration")
        audio_duration = audio_info.get("duration", 0.0)

        if duration is not None:
            if duration > audio_duration:
                raise FFmpegValidationError(
                    f"Duration ({duration}s) exceeds audio length ({audio_duration}s)"
                )
        elif offset >= audio_duration:
            raise FFmpegValidationError(
                f"Offset ({offset}s) exceeds audio length ({audio_duration}s)"
            )

    def _generate_ffmpeg_command_replace(
        self,
        video_path: str,
        audio_path: str,
        output_file: str,
    ) -> List[str]:
        """
        Генерация команды FFmpeg для замены аудио дорожки.

        Использует -c:v copy для копирования видео без перекодирования
        и -c:a aac для кодирования аудио в AAC.

        Args:
            video_path: Путь к видеофайлу
            audio_path: Путь к аудиофайлу
            output_file: Путь к выходному файлу

        Returns:
            Список аргументов для FFmpeg
        """
        from app.config import get_settings
        settings = get_settings()
        ffmpeg = getattr(settings, "FFMPEG_PATH", "ffmpeg")

        return [
            ffmpeg,
            "-y",  # Перезаписать выходной файл
            "-i", video_path,  # Входное видео
            "-i", audio_path,  # Входное аудио
            "-map", "0:v:0",  # Видео из первого входа
            "-map", "1:a:0",  # Аудио из второго входа
            "-c:v", "copy",  # Копировать видео без перекодирования
            "-c:a", "aac",  # Кодировать аудио в AAC
            "-shortest",  # Обрезать по самому короткому потоку
            output_file,
        ]

    def _generate_ffmpeg_command_mix(
        self,
        video_path: str,
        audio_path: str,
        output_file: str,
    ) -> List[str]:
        """
        Генерация команды FFmpeg для смешивания аудио.

        Использует amix фильтр для смешивания и volume фильтры для регулировки громкости.

        Args:
            video_path: Путь к видеофайлу
            audio_path: Путь к аудиофайлу
            output_file: Путь к выходному файлу

        Returns:
            Список аргументов для FFmpeg
        """
        from app.config import get_settings
        settings = get_settings()
        ffmpeg = getattr(settings, "FFMPEG_PATH", "ffmpeg")

        original_volume = self.config.get("original_volume", 1.0)
        overlay_volume = self.config.get("overlay_volume", 1.0)
        offset = self.config.get("offset", 0.0)
        duration = self.config.get("duration")

        # Создаем фильтр для смешивания аудио
        # Сначала применяем volume к каждому аудио потоку, затем смешиваем
        if duration is not None:
            # Обрезаем аудио до указанной длительности
            filter_complex = (
                f"[1:a]volume={overlay_volume}[a1];"
                f"[0:a]volume={original_volume}[a0];"
                f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=2"
            )
        else:
            filter_complex = (
                f"[1:a]volume={overlay_volume}[a1];"
                f"[0:a]volume={original_volume}[a0];"
                f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=2"
            )

        cmd = [
            ffmpeg,
            "-y",  # Перезаписать выходной файл
            "-i", video_path,  # Входное видео
            "-ss", str(offset),  # Смещение аудио
            "-i", audio_path,  # Входное аудио
            "-filter_complex", filter_complex,  # Комплексный фильтр
            "-c:v", "copy",  # Копировать видео без перекодирования
            "-c:a", "aac",  # Кодировать аудио в AAC
        ]

        if duration is not None:
            cmd.extend(["-t", str(duration)])

        cmd.append(output_file)
        return cmd

    async def process_replace(self) -> Dict[str, Any]:
        """
        Замена аудио дорожки в видео.

        Returns:
            Словарь с путем к выходному файлу
        """
        video_path = self.config.get("video_path")
        audio_path = self.config.get("audio_path")
        output_path = self.config.get("output_path")

        if not output_path:
            output_path = create_temp_file(suffix=".mp4", prefix="audio_overlay_")
            self.add_temp_file(output_path)

        cmd = self._generate_ffmpeg_command_replace(video_path, audio_path, output_path)

        # Получаем длительность видео для расчета прогресса
        video_info = await FFmpegCommand.get_video_info(video_path)
        total_duration = video_info.get("duration", 0.0)

        def progress_cb(progress: float) -> None:
            if total_duration and total_duration > 0 and progress is not None:
                pct = min(100.0, max(0.0, 100.0 * progress / total_duration))
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

    async def process_mix(self) -> Dict[str, Any]:
        """
        Смешивание аудио дорожки с оригиналом.

        Returns:
            Словарь с путем к выходному файлу
        """
        video_path = self.config.get("video_path")
        audio_path = self.config.get("audio_path")
        output_path = self.config.get("output_path")

        if not output_path:
            output_path = create_temp_file(suffix=".mp4", prefix="audio_overlay_")
            self.add_temp_file(output_path)

        cmd = self._generate_ffmpeg_command_mix(video_path, audio_path, output_path)

        # Получаем длительность видео для расчета прогресса
        video_info = await FFmpegCommand.get_video_info(video_path)
        total_duration = video_info.get("duration", 0.0)

        def progress_cb(progress: float) -> None:
            if total_duration and total_duration > 0 and progress is not None:
                pct = min(100.0, max(0.0, 100.0 * progress / total_duration))
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

    async def process(self) -> Dict[str, Any]:
        """
        Основная обработка. Выбирает режим replace или mix в зависимости от конфигурации.

        Returns:
            Словарь с путем к выходному файлу
        """
        mode = self.config.get("mode", "replace")

        if mode == "replace":
            return await self.process_replace()
        elif mode == "mix":
            return await self.process_mix()
        else:
            raise FFmpegValidationError(f"Unknown mode: {mode}")
