"""
Subtitle Pydantic schemas for API request/response
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from app.schemas.common import FileSource


class SubtitleFormat(str, Enum):
    """Поддерживаемые форматы субтитров"""

    SRT = "SRT"
    VTT = "VTT"
    ASS = "ASS"
    SSA = "SSA"


class SubtitleStyle(BaseModel):
    """Настройки стиля субтитров (для ASS/SSA форматов)"""

    font_name: str = Field(default="Arial", description="Имя шрифта")
    font_size: int = Field(default=20, ge=10, le=72, description="Размер шрифта")

    primary_color: str = Field(
        default="&H00FFFFFF",
        pattern=r"^&H[0-9A-Fa-f]{8}$",
        description="Основной цвет текста в формате &HAABBGGRR",
    )
    secondary_color: str = Field(
        default="&H000000FF",
        pattern=r"^&H[0-9A-Fa-f]{8}$",
        description="Вторичный цвет для karaoke",
    )
    outline_color: str = Field(
        default="&H00000000",
        pattern=r"^&H[0-9A-Fa-f]{8}$",
        description="Цвет обводки",
    )
    back_color: str = Field(
        default="&H80000000",
        pattern=r"^&H[0-9A-Fa-f]{8}$",
        description="Цвет фона (shadow box)",
    )

    bold: bool = Field(default=False, description="Жирный шрифт")
    italic: bool = Field(default=False, description="Курсив")
    underline: bool = Field(default=False, description="Подчеркивание")
    strikeout: bool = Field(default=False, description="Зачеркивание")

    scale_x: float = Field(default=1.0, ge=0.0, le=10.0, description="Масштаб по X")
    scale_y: float = Field(default=1.0, ge=0.0, le=10.0, description="Масштаб по Y")

    spacing: float = Field(default=0.0, ge=-10.0, le=10.0, description="Межсимвольный интервал")

    angle: float = Field(default=0.0, ge=-360.0, le=360.0, description="Угол поворота текста")

    border_style: int = Field(default=1, ge=0, le=4, description="Стиль обводки")

    outline: float = Field(default=2.0, ge=0.0, description="Толщина обводки")
    shadow: float = Field(default=2.0, ge=0.0, description="Глубина тени")

    alignment: int = Field(default=2, ge=1, le=9, description="Выравнивание (1-9 как на Numpad)")

    margin_l: int = Field(default=10, ge=0, description="Отступ слева")
    margin_r: int = Field(default=10, ge=0, description="Отступ справа")
    margin_v: int = Field(default=10, ge=0, description="Вертикальный отступ")

    encoding: int = Field(default=1, ge=0, le=255, description="Кодировка текста")

    @field_validator("primary_color", "secondary_color", "outline_color", "back_color")
    @classmethod
    def validate_color_format(cls, v: str) -> str:
        """Проверка формата цвета &HAABBGGRR"""
        if not v.startswith("&H") or len(v) != 10:
            raise ValueError('Color must be in format &HAABBGGRR (8 hex chars)')
        return v


class SubtitlePosition(BaseModel):
    """Позиционирование субтитров"""

    position: Optional[str] = Field(
        default=None,
        description="Позиция: top, center, bottom",
    )
    margin_x: int = Field(default=10, ge=0, description="Горизонтальный отступ")
    margin_y: int = Field(default=10, ge=0, description="Вертикальный отступ")

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: Optional[str]) -> Optional[str]:
        """Проверка допустимых значений позиции"""
        if v is not None and v not in ["top", "center", "bottom"]:
            raise ValueError('Position must be one of: top, center, bottom')
        return v


class SubtitleRequest(BaseModel):
    """Запрос на наложение субтитров"""

    video_file_id: FileSource = Field(..., description="ID or URL of the video file")
    subtitle_file_id: Optional[FileSource] = Field(default=None, description="ID or URL of the subtitle file (if present)")
    subtitle_text: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Текст субтитров в формате [{start, end, text}, ...]",
    )
    format: SubtitleFormat = Field(default=SubtitleFormat.SRT, description="Формат субтитров")
    style: SubtitleStyle = Field(default_factory=SubtitleStyle, description="Стиль субтитров")
    position: SubtitlePosition = Field(default_factory=SubtitlePosition, description="Позиционирование")
    output_filename: Optional[str] = Field(default=None, description="Имя выходного файла")

    @field_validator("subtitle_text")
    @classmethod
    def validate_subtitle_text(cls, v: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
        """Проверка формата текста субтитров"""
        if v is None:
            return None
        for i, entry in enumerate(v):
            if not isinstance(entry, dict):
                raise ValueError(f"Subtitle entry {i} must be a dict")
            if "start" not in entry:
                raise ValueError(f"Subtitle entry {i} missing 'start' field")
            if "end" not in entry:
                raise ValueError(f"Subtitle entry {i} missing 'end' field")
            if "text" not in entry:
                raise ValueError(f"Subtitle entry {i} missing 'text' field")
            if not isinstance(entry["start"], (int, float)):
                raise ValueError(f"Subtitle entry {i} 'start' must be a number")
            if not isinstance(entry["end"], (int, float)):
                raise ValueError(f"Subtitle entry {i} 'end' must be a number")
            if not isinstance(entry["text"], str):
                raise ValueError(f"Subtitle entry {i} 'text' must be a string")
            if entry["start"] >= entry["end"]:
                raise ValueError(f"Subtitle entry {i} start time must be less than end time")
        return v

    @field_validator("subtitle_file_id")
    @classmethod
    def validate_subtitle_source(cls, v: Optional[FileSource], info) -> Optional[FileSource]:
        """Проверка, что указан хотя бы один источник субтитров"""
        if v is None:
            subtitle_text = info.data.get("subtitle_text")
            if subtitle_text is None:
                raise ValueError("Either subtitle_file_id or subtitle_text must be provided")
        return v
