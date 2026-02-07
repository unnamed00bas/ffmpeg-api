"""
Audio overlay Pydantic schemas for API request/response
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field
from app.schemas.common import FileSource


class AudioOverlayMode(str, Enum):
    """Режим наложения аудио"""

    REPLACE = "replace"  # Заменить оригинальное аудио
    MIX = "mix"  # Смешать с оригинальным аудио


class AudioOverlayRequest(BaseModel):
    """
    Схема запроса наложения аудио

    Attributes:
        video_file_id: ID видеофайла
        audio_file_id: ID аудиофайла
        mode: Режим наложения (replace или mix)
        offset: Смещение начала аудио в секундах (>= 0)
        duration: Длительность накладываемого аудио в секундах (опционально, >= 0)
        original_volume: Громкость оригинального аудио (0-2)
        overlay_volume: Громкость накладываемого аудио (0-2)
        output_filename: Имя выходного файла (опционально)
    """

    video_file_id: FileSource = Field(..., description="ID or URL of the video file")
    audio_file_id: FileSource = Field(..., description="ID or URL of the audio file")
    mode: AudioOverlayMode = Field(
        default=AudioOverlayMode.REPLACE,
        description="Режим наложения (replace или mix)",
    )
    offset: float = Field(
        default=0.0, ge=0.0, description="Смещение начала аудио в секундах"
    )
    duration: Optional[float] = Field(
        None, ge=0.0, description="Длительность накладываемого аудио в секундах"
    )
    original_volume: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Громкость оригинального аудио (0-2)",
    )
    overlay_volume: float = Field(
        default=1.0,
        ge=0.0,
        le=2.0,
        description="Громкость накладываемого аудио (0-2)",
    )
    output_filename: Optional[str] = Field(
        None, description="Имя выходного файла"
    )
