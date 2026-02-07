"""
Video join processor: concat demuxer, optional optimization via FFmpegOptimizer and caching.
"""
from typing import Any, Dict, List, Optional

from app.ffmpeg.commands import (
    FFmpegCommand,
    FFmpegOptimizer,
    FFmpegPreset,
    FFmpegTune,
)
from app.ffmpeg.exceptions import FFmpegValidationError
from app.processors.base_processor import BaseProcessor
from app.utils.temp_files import create_temp_file, create_temp_dir


class VideoJoiner(BaseProcessor):
    """Объединение нескольких видео в один через FFmpeg concat demuxer (-c copy) + оптимизации."""

    def __init__(
        self,
        task_id: int,
        config: Dict[str, Any],
        progress_callback: Optional[Any] = None,
        cache_service: Optional[Any] = None,  # CacheService
    ):
        super().__init__(task_id, config, progress_callback)
        self.cache_service = cache_service
        self.video_metadata_cache = None
        self.operation_result_cache = None
        if cache_service:
            from app.cache.cache_service import (
                VideoMetadataCache,
                OperationResultCache,
            )
            self.video_metadata_cache = VideoMetadataCache(cache_service)
            self.operation_result_cache = OperationResultCache(cache_service)

    async def validate_input(self) -> None:
        """Проверка: минимум 2 файла, совпадение разрешения, FPS, кодека; кэширование метаданных."""
        file_paths = self.config.get("input_paths") or []
        if len(file_paths) < 2:
            raise FFmpegValidationError("At least 2 input files required")
        infos = []
        for i, path in enumerate(file_paths):
            # Попытка взять из кэша
            info = None
            if self.video_metadata_cache:
                # file_id берем из конфига; если нет — используем индекс
                file_ids = self.config.get("file_ids") or []
                file_id = file_ids[i] if i < len(file_ids) else i
                cached = await self.video_metadata_cache.get_video_info(
                    file_id,
                    path,
                )
                if cached:
                    info = cached
            if not info:
                info = await FFmpegCommand.get_video_info(path)
                # Сохранить в кэш
                if self.video_metadata_cache:
                    await self.video_metadata_cache.set_video_info(file_id, path, info)
            infos.append(info)
        # Проверка совпадения разрешения и кодека
        w, h = infos[0].get("width"), infos[0].get("height")
        codec = infos[0].get("video_codec")
        fps = infos[0].get("fps")
        for i, info in enumerate(infos[1:], 1):
            if info.get("width") != w or info.get("height") != h:
                raise FFmpegValidationError(
                    f"Video {i+1} has different resolution: {info.get('width')}x{info.get('height')}"
                )
            if info.get("video_codec") != codec:
                raise FFmpegValidationError(
                    f"Video {i+1} has different codec: {info.get('video_codec')}"
                )
            if fps is not None and info.get("fps") is not None:
                if abs((info.get("fps") or 0) - fps) > 0.1:
                    raise FFmpegValidationError(
                        f"Video {i+1} has different FPS: {info.get('fps')}"
                    )

    async def _create_concat_list(self, video_files: List[str]) -> str:
        """Создание файла со списком путей для concat demuxer (формат: file 'path')."""
        temp_dir = create_temp_dir()
        self.add_temp_file(temp_dir)
        concat_path = create_temp_file(suffix=".txt", prefix="concat_", directory=temp_dir)
        self.add_temp_file(concat_path)
        lines = []
        for path in video_files:
            # Экранирование одинарных кавычек в пути: ' -> '\''
            escaped = path.replace("'", "'\\''")
            lines.append(f"file '{escaped}'")
        with open(concat_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return concat_path

    def _generate_ffmpeg_command(
        self,
        concat_list: str,
        output_file: str,
    ) -> List[str]:
        """Генерация команды FFmpeg для concat demuxer с оптимизациями."""
        from app.config import get_settings
        settings = get_settings()
        ffmpeg = getattr(settings, "FFMPEG_PATH", "ffmpeg")
        command = [
            ffmpeg,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
        ]
        # Оптимизации из конфига
        opt_config = self.config.get("optimization", {})
        scenario = opt_config.get("scenario")  # "fast", "balanced", "quality" или None
        if scenario:
            optimizer = FFmpegOptimizer()
            opt_params = optimizer.optimize_for_scenario(scenario)
            # Создаем оптимизатор по параметрам из сценария
            optimizer_scenario = FFmpegOptimizer(
                preset=opt_params.get("preset", FFmpegPreset.FAST),
                tune=opt_params.get("tune"),
                crf=opt_params.get("crf"),
                threads=opt_params.get("threads"),
            )
            # Для concat demuxer (copy) оптимизаторы не применяются,
            # но если в будущем потребуется перекодирование — параметры будут готовы.
        # Для простоты, при concat demuxer не добавляем -preset, -tune, -crf.
        # Но оставим место для возможного кодирования в будущем.
        command.extend(["-c", "copy"])
        command.append(output_file)
        return command

    async def process(self) -> Dict[str, Any]:
        """Объединение видео: concat list -> FFmpeg -> выходной файл; с кэшированием результата."""
        input_paths = self.config.get("input_paths") or []
        file_ids = self.config.get("file_ids") or []
        output_path = self.config.get("output_path")
        if not output_path:
            output_path = create_temp_file(suffix=".mp4", prefix="joined_")
            self.add_temp_file(output_path)

        # Попытка взять результат из кэша
        cached_result = None
        if self.operation_result_cache and file_ids:
            try:
                cached_result = await self.operation_result_cache.get_result(
                    "join",
                    file_ids,
                    self.config,
                )
            except Exception:
                pass
        if cached_result:
            # Если кэш содержит результат, можно либо:
            # 1) вернуть его если файл существует в MinIO; или
            # 2) для простоты здесь считаем, что concat демуксер без перекодирования
            #    быстр и результат кэш-предсказуем — возвращаем "ссылка".
            self.update_progress(100)
            return cached_result

        concat_list = await self._create_concat_list(input_paths)
        cmd = self._generate_ffmpeg_command(concat_list, output_path)

        total_duration = 0.0
        try:
            for path in input_paths:
                info = await FFmpegCommand.get_video_info(path)
                total_duration += info.get("duration") or 0
        except Exception:
            pass

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
        result = {"output_path": output_path}
        # Сохранение результата в кэш
        if self.operation_result_cache and file_ids:
            try:
                await self.operation_result_cache.set_result(
                    "join",
                    file_ids,
                    self.config,
                    result,
                )
            except Exception:
                pass
        return result