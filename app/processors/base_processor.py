"""
Base processor for FFmpeg-based tasks
"""
import os
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional


class BaseProcessor(ABC):
    """Базовый класс процессора: валидация, процесс, очистка временных файлов."""

    def __init__(
        self,
        task_id: int,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None,
    ):
        self.task_id = task_id
        self.config = config
        self.progress_callback = progress_callback
        self.temp_files: List[str] = []

    @abstractmethod
    async def validate_input(self) -> None:
        """Валидация входных данных. Должен выбросить исключение при ошибке."""
        pass

    @abstractmethod
    async def process(self) -> Dict[str, Any]:
        """Основная обработка. Возвращает словарь результата."""
        pass

    async def run(self) -> Dict[str, Any]:
        """Запуск: validate_input -> process -> cleanup."""
        await self.validate_input()
        try:
            result = await self.process()
            return result
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Удаление временных файлов из self.temp_files."""
        for path in self.temp_files:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        self.temp_files.clear()

    def update_progress(self, progress: float) -> None:
        """Вызов progress_callback с прогрессом 0.0–100.0."""
        if self.progress_callback:
            self.progress_callback(progress)

    def add_temp_file(self, file_path: str) -> None:
        """Добавить путь во временные файлы для последующей очистки."""
        self.temp_files.append(file_path)
