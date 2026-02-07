"""
Pydantic schemas for text overlay feature
"""
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import FileSource


class TextPositionType(str, Enum):
    """Text position type enumeration"""
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


class TextPosition(BaseModel):
    """Text position configuration"""
    type: TextPositionType = TextPositionType.RELATIVE
    # For absolute positioning
    x: Optional[int] = None
    y: Optional[int] = None
    # For relative positioning
    position: Optional[str] = Field(
        default="center",
        description="Relative position: top-left, top-center, top-right, center-left, center, center-right, bottom-left, bottom-center, bottom-right"
    )
    margin_x: int = Field(default=10, ge=0)
    margin_y: int = Field(default=10, ge=0)

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: Optional[str]) -> Optional[str]:
        """Validate relative position value"""
        if v is None:
            return "center"
        valid_positions = [
            "top-left", "top-center", "top-right",
            "center-left", "center", "center-right",
            "bottom-left", "bottom-center", "bottom-right"
        ]
        if v not in valid_positions:
            raise ValueError(f"Position must be one of: {', '.join(valid_positions)}")
        return v


class TextStyle(BaseModel):
    """Text style configuration"""
    font_family: str = Field(default="Arial", min_length=1)
    font_size: int = Field(default=24, ge=8, le=200)
    font_weight: str = Field(
        default="normal",
        pattern=r"^(normal|bold|100|200|300|400|500|600|700|800|900)$"
    )
    color: str = Field(
        default="white",
        pattern=r"^#[0-9A-Fa-f]{6}$"
    )
    alpha: float = Field(default=1.0, ge=0.0, le=1.0)


class TextBackground(BaseModel):
    """Text background configuration"""
    enabled: bool = False
    color: str = Field(
        default="black",
        pattern=r"^#[0-9A-Fa-f]{6}$"
    )
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    padding: int = Field(default=10, ge=0)
    border_radius: int = Field(default=5, ge=0)


class TextBorder(BaseModel):
    """Text border configuration"""
    enabled: bool = False
    width: int = Field(default=2, ge=0)
    color: str = Field(
        default="black",
        pattern=r"^#[0-9A-Fa-f]{6}$"
    )


class TextShadow(BaseModel):
    """Text shadow configuration"""
    enabled: bool = False
    offset_x: int = Field(default=2, ge=-50, le=50)
    offset_y: int = Field(default=2, ge=-50, le=50)
    blur: int = Field(default=2, ge=0, le=20)
    color: str = Field(
        default="black",
        pattern=r"^#[0-9A-Fa-f]{6}$"
    )


class TextAnimationType(str, Enum):
    """Text animation type enumeration"""
    NONE = "none"
    FADE_IN = "fade_in"
    FADE_OUT = "fade_out"
    FADE = "fade"
    SLIDE_LEFT = "slide_left"
    SLIDE_RIGHT = "slide_right"
    SLIDE_UP = "slide_up"
    SLIDE_DOWN = "slide_down"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"


class TextAnimation(BaseModel):
    """Text animation configuration"""
    type: TextAnimationType = TextAnimationType.NONE
    duration: float = Field(default=1.0, ge=0.0)
    delay: float = Field(default=0.0, ge=0.0)


class TextOverlayRequest(BaseModel):
    """Request for text overlay operation"""
    video_file_id: FileSource = Field(..., description="ID or URL of the video file")
    text: str = Field(..., min_length=1, max_length=1000)
    position: TextPosition = Field(default_factory=TextPosition)
    style: TextStyle = Field(default_factory=TextStyle)
    background: TextBackground = Field(default_factory=TextBackground)
    border: TextBorder = Field(default_factory=TextBorder)
    shadow: TextShadow = Field(default_factory=TextShadow)
    animation: TextAnimation = Field(default_factory=TextAnimation)
    rotation: int = Field(default=0, ge=-360, le=360)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)
    start_time: float = Field(default=0.0, ge=0.0)
    end_time: Optional[float] = Field(default=None, ge=0.0)
    output_filename: Optional[str] = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        """Validate text for special characters that may cause issues"""
        if not v or not v.strip():
            raise ValueError("Text cannot be empty")
        return v


__all__ = [
    "TextPositionType",
    "TextPosition",
    "TextStyle",
    "TextBackground",
    "TextBorder",
    "TextShadow",
    "TextAnimationType",
    "TextAnimation",
    "TextOverlayRequest",
]
