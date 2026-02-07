"""
Temporary file management for FFmpeg processing
"""
import os
import tempfile
import time
from typing import List, Optional


def create_temp_file(
    suffix: str = "",
    prefix: str = "ffmpeg_",
    directory: Optional[str] = None,
) -> str:
    """
    Создание временного файла.

    Args:
        suffix: Суффикс имени (например, расширение .mp4)
        prefix: Префикс имени
        directory: Директория (если None — системная temp)

    Returns:
        Путь к созданному файлу
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=directory)
    os.close(fd)
    return path


def create_temp_dir(
    prefix: str = "ffmpeg_",
    suffix: str = "",
) -> str:
    """
    Создание временной директории.

    Args:
        prefix: Префикс имени
        suffix: Суффикс имени

    Returns:
        Путь к созданной директории
    """
    return tempfile.mkdtemp(suffix=suffix, prefix=prefix)


def cleanup_temp_files(temp_files: List[str]) -> None:
    """
    Удаление переданных временных файлов.
    Несуществующие пути игнорируются.

    Args:
        temp_files: Список путей к файлам
    """
    for path in temp_files:
        try:
            if os.path.exists(path) and os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


def cleanup_old_files(
    directory: str,
    max_age_hours: int = 24,
) -> int:
    """
    Удаление файлов и директорий в directory старше max_age_hours.
    Обрабатываются только элементы с префиксом ffmpeg_.

    Args:
        directory: Директория для очистки
        max_age_hours: Максимальный возраст в часах

    Returns:
        Количество удалённых файлов/директорий
    """
    if not os.path.isdir(directory):
        return 0

    count = 0
    now = time.time()
    max_age_seconds = max_age_hours * 3600

    try:
        for name in os.listdir(directory):
            if not name.startswith("ffmpeg_"):
                continue
            path = os.path.join(directory, name)
            try:
                stat = os.stat(path)
                if now - stat.st_mtime > max_age_seconds:
                    if os.path.isfile(path):
                        os.remove(path)
                        count += 1
                    elif os.path.isdir(path):
                        import shutil
                        shutil.rmtree(path, ignore_errors=True)
                        count += 1
            except OSError:
                pass
    except OSError:
        pass

    return count
