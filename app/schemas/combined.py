"""
Combined operations Pydantic schemas
"""
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field
from app.schemas.common import FileSource


class OperationType(str, Enum):
    """Типы операций для комбинированной обработки"""
    JOIN = "join"
    AUDIO_OVERLAY = "audio_overlay"
    TEXT_OVERLAY = "text_overlay"
    SUBTITLES = "subtitles"
    VIDEO_OVERLAY = "video_overlay"


class Operation(BaseModel):
    """Операция в комбинированном pipeline"""
    type: OperationType
    config: Dict[str, Any] = Field(default_factory=dict)


class CombinedRequest(BaseModel):
    """Запрос на комбинированные операции"""
    operations: List[Operation] = Field(..., min_length=2, max_length=10)
    base_file_id: FileSource
    output_filename: Optional[str] = None
