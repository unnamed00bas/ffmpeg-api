"""
Combined operations processor: executes multiple operations in a pipeline
"""
import os
from typing import Any, Callable, Dict, List, Optional

from app.ffmpeg.exceptions import FFmpegValidationError
from app.processors.base_processor import BaseProcessor
from app.utils.temp_files import create_temp_file
from app.ffmpeg.commands import FFmpegCommand


# Import processors when they are implemented
# from app.processors.audio_overlay import AudioOverlay
# from app.processors.text_overlay import TextOverlay
# from app.processors.subtitle_processor import SubtitleProcessor
# from app.processors.video_overlay import VideoOverlay


class CombinedProcessor(BaseProcessor):
    """
    Процессор для выполнения комбинированных операций в pipeline.
    
    Выполняет операции последовательно, передавая результат одной операции
    в качестве входных данных для следующей.
    """

    def __init__(
        self,
        task_id: int,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None,
    ):
        super().__init__(task_id, config, progress_callback)
        self.intermediate_files: List[str] = []

    async def validate_input(self) -> None:
        """
        Валидация входных данных pipeline.
        
        Проверяет:
        - Количество операций (2-10)
        - Совместимость типов операций
        - Наличие и корректность base_file_id
        """
        operations = self.config.get("operations", [])
        
        # Проверка количества операций
        if len(operations) < 2:
            raise FFmpegValidationError("At least 2 operations required for combined processing")
        if len(operations) > 10:
            raise FFmpegValidationError("Maximum 10 operations allowed")
        
        # Проверка base_file_id
        base_file_id = self.config.get("base_file_id")
        if not base_file_id or not isinstance(base_file_id, int):
            raise FFmpegValidationError("base_file_id is required and must be an integer")
        
        # Проверка типов операций
        valid_types = {"join", "audio_overlay", "text_overlay", "subtitles", "video_overlay"}
        for i, operation in enumerate(operations):
            op_type = operation.get("type")
            if op_type not in valid_types:
                raise FFmpegValidationError(
                    f"Invalid operation type at position {i}: {op_type}. "
                    f"Valid types: {', '.join(valid_types)}"
                )
            
            # Проверка наличия config
            if not isinstance(operation.get("config"), dict):
                raise FFmpegValidationError(
                    f"Operation config must be a dictionary at position {i}"
                )
        
        # Проверка совместимости операций
        # JOIN может быть только первой операцией (так как он создает новый файл из нескольких)
        if operations and operations[0].get("type") == "join":
            # Это допустимо, но требует специальной обработки
            pass

    async def process(self) -> Dict[str, Any]:
        """
        Основная обработка: выполнение pipeline операций.
        
        Returns:
            Словарь с result_file_id и operations_count
        """
        operations = self.config.get("operations", [])
        base_file_id = self.config.get("base_file_id")
        
        # Загрузка base файла
        current_file = await self._load_file(base_file_id)
        self.add_temp_file(current_file)
        
        # Выполнение операций последовательно
        for i, operation in enumerate(operations):
            # Обновление прогресса
            progress = (i / len(operations)) * 100
            self.update_progress(progress)
            
            try:
                # Выполнение операции
                result_file = await self._execute_operation(
                    operation,
                    current_file
                )
                
                # Удаление предыдущего файла после успешной операции
                if current_file in self.temp_files:
                    self.temp_files.remove(current_file)
                if os.path.exists(current_file):
                    os.remove(current_file)
                
                # Обновление текущего файла
                current_file = result_file
                self.add_temp_file(current_file)
                
            except Exception as e:
                # Откат при ошибке
                await self._rollback()
                raise
        
        # Финальное обновление прогресса
        self.update_progress(100.0)
        
        # Загрузка результата в MinIO и создание записи в БД
        result_file_id = await self._upload_result(current_file)
        
        return {
            "result_file_id": result_file_id,
            "operations_count": len(operations)
        }

    async def _execute_operation(
        self,
        operation: Dict[str, Any],
        input_file: str
    ) -> str:
        """
        Выполнение одной операции pipeline.
        
        Args:
            operation: Словарь с type и config
            input_file: Путь к входному файлу
            
        Returns:
            Путь к выходному файлу операции
        """
        op_type = operation.get("type")
        op_config = operation.get("config", {}).copy()
        
        # Создание процессора в зависимости от типа операции
        processor = await self._create_processor(op_type, op_config)
        
        # Валидация операции
        await processor.validate_input()
        
        # Подготовка конфигурации с input_file
        # Для overlay операций input_file может быть video_file_id или аналогично
        self._prepare_processor_config(processor, op_type, op_config, input_file)
        
        # Выполнение операции
        result = await processor.process()
        
        # Получение пути к выходному файлу из результата
        output_file = self._extract_output_file(result, op_type)
        
        # Добавление в intermediate files для отслеживания
        self.intermediate_files.append(output_file)
        
        return output_file

    async def _create_processor(
        self,
        op_type: str,
        op_config: Dict[str, Any]
    ) -> BaseProcessor:
        """
        Создание процессора для операции.
        
        Args:
            op_type: Тип операции
            op_config: Конфигурация операции
            
        Returns:
            Экземпляр процессора
        """
        # Загружаем процессоры динамически, чтобы избежать ошибок импорта
        # если они еще не реализованы
        processors_map = {
            "audio_overlay": ("app.processors.audio_overlay", "AudioOverlay"),
            "text_overlay": ("app.processors.text_overlay", "TextOverlay"),
            "subtitles": ("app.processors.subtitle_processor", "SubtitleProcessor"),
            "video_overlay": ("app.processors.video_overlay", "VideoOverlay"),
        }
        
        if op_type == "join":
            # Для join используем VideoJoiner
            from app.processors.video_joiner import VideoJoiner
            return VideoJoiner(
                task_id=self.task_id,
                config=op_config,
                progress_callback=None  # Без прогресса для отдельных операций
            )
        
        if op_type not in processors_map:
            raise FFmpegValidationError(f"Unsupported operation type: {op_type}")
        
        module_name, class_name = processors_map[op_type]
        
        try:
            # Динамический импорт
            import importlib
            module = importlib.import_module(module_name)
            processor_class = getattr(module, class_name)
            
            return processor_class(
                task_id=self.task_id,
                config=op_config,
                progress_callback=None
            )
        except ImportError as e:
            raise FFmpegValidationError(
                f"Processor for {op_type} not implemented yet. "
                f"Please implement {module_name}.{class_name}"
            )
        except Exception as e:
            raise FFmpegValidationError(
                f"Failed to create processor for {op_type}: {str(e)}"
            )

    def _prepare_processor_config(
        self,
        processor: BaseProcessor,
        op_type: str,
        op_config: Dict[str, Any],
        input_file: str
    ) -> None:
        """
        Подготовка конфигурации процессора с input_file.
        
        Args:
            processor: Экземпляр процессора
            op_type: Тип операции
            op_config: Исходная конфигурация
            input_file: Путь к входному файлу
        """
        # Разные процессоры ожидают разные параметры для входного файла
        if op_type == "join":
            # Для join всегда начинаем с текущего файла в pipeline (input_file)
            input_paths = [input_file]
            # Добавляем дополнительные файлы, если переданы из tasks.py или конфига
            if "secondary_input_paths" in op_config:
                input_paths.extend(op_config["secondary_input_paths"])
            # Если были переданы input_paths напрямую (например, не из pipeline), они будут перезаписаны,
            # но мы предполагаем pipeline-логику, где input_file всегда первый.
            op_config["input_paths"] = input_paths
        elif op_type == "audio_overlay":
            op_config["video_path"] = input_file
        elif op_type == "text_overlay":
            op_config["video_path"] = input_file
        elif op_type == "subtitles":
            op_config["video_path"] = input_file
        elif op_type == "video_overlay":
            op_config["base_file_path"] = input_file
        
        # Обновляем конфигурацию процессора
        processor.config.update(op_config)

    def _extract_output_file(
        self,
        result: Dict[str, Any],
        op_type: str
    ) -> str:
        """
        Извлечение пути к выходному файлу из результата операции.
        
        Args:
            result: Результат выполнения операции
            op_type: Тип операции
            
        Returns:
            Путь к выходному файлу
        """
        # Разные процессоры могут возвращать разные ключи
        possible_keys = ["output_path", "output_file", "result_file"]
        
        for key in possible_keys:
            if key in result and result[key]:
                file_path = result[key]
                if isinstance(file_path, str) and os.path.exists(file_path):
                    return file_path
        
        raise FFmpegValidationError(
            f"Operation {op_type} did not return a valid output file. "
            f"Result keys: {list(result.keys())}"
        )

    async def _load_file(self, file_id: int) -> str:
        """
        Загрузка файла из MinIO во временную директорию.
        
        Args:
            file_id: ID файла в базе данных
            
        Returns:
            Путь к загруженному файлу
        """
        from app.storage.minio_client import MinIOClient
        from app.database.connection import get_db_sync
        from app.database.models.file import File
        from sqlalchemy.orm import Session
        
        db: Session = get_db_sync()
        try:
            file_record = db.query(File).filter(File.id == file_id).first()
            if not file_record:
                raise FFmpegValidationError(f"File with ID {file_id} not found")
            
            storage = MinIOClient()
            
            # Создание временного файла
            ext = file_record.original_filename.rsplit(".", 1)[-1] if "." in file_record.original_filename else "mp4"
            temp_path = create_temp_file(suffix=f".{ext}", prefix=f"input_{file_id}_")
            
            # Скачивание файла
            await storage.download_file(
                file_record.storage_path,
                temp_path
            )
            
            return temp_path
        finally:
            db.close()

    async def _upload_result(self, file_path: str) -> int:
        """
        Загрузка результата в MinIO и создание записи в БД.
        
        Args:
            file_path: Путь к файлу результата
            
        Returns:
            ID созданного файла
        """
        import uuid
        from datetime import datetime
        from app.storage.minio_client import MinIOClient
        from app.database.connection import get_db_sync
        from app.database.models.file import File
        from sqlalchemy.orm import Session
        
        db: Session = get_db_sync()
        try:
            storage = MinIOClient()
            
            # Определение имени файла и content type
            output_filename = self.config.get("output_filename", f"combined_{self.task_id}.mp4")
            object_name = f"{self.task_id}/combined_{uuid.uuid4().hex}_{output_filename}"
            content_type = "video/mp4"
            
            # Загрузка в MinIO
            await storage.upload_file(
                file_path=file_path,
                object_name=object_name,
                content_type=content_type
            )
            
            # Получение размера файла
            file_size = os.path.getsize(file_path)
            
            # Создание записи в БД
            new_file = File(
                user_id=self.config.get("user_id", 0),  # Должен быть передан в config
                filename=object_name,
                original_filename=output_filename,
                size=file_size,
                content_type=content_type,
                storage_path=object_name,
            )
            
            db.add(new_file)
            db.commit()
            db.refresh(new_file)
            
            return new_file.id
        finally:
            db.close()

    async def _rollback(self) -> None:
        """Откат при ошибке: очистка всех временных файлов."""
        await self.cleanup()

    async def cleanup(self) -> None:
        """
        Очистка всех временных файлов.
        
        Удаляет:
        - Базовые temp файлы (из родительского класса)
        - Intermediate файлы (промежуточные результаты)
        """
        # Очистка базовых temp файлов
        await super().cleanup()
        
        # Удаление intermediate files
        for intermediate_file in self.intermediate_files:
            try:
                if os.path.exists(intermediate_file):
                    os.remove(intermediate_file)
            except OSError:
                pass
        
        # Очистка списка intermediate files
        self.intermediate_files.clear()
