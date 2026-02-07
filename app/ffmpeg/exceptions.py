"""
FFmpeg-related exceptions
"""


class FFmpegError(Exception):
    """Базовое исключение FFmpeg."""

    pass


class FFmpegValidationError(FFmpegError):
    """Ошибка валидации входных данных/файлов."""

    pass


class FFmpegProcessingError(FFmpegError):
    """Ошибка во время обработки (код возврата FFmpeg)."""

    pass


class FFmpegTimeoutError(FFmpegError):
    """Таймаут выполнения команды FFmpeg."""

    pass
