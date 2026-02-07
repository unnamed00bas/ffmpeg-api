"""
Pydantic schemas for Video Overlay (Picture-in-Picture) feature
"""
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator
from app.schemas.common import FileSource


class OverlayShapeType(str, Enum):
    """Shape types for video overlay"""
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ROUNDED = "rounded"


class OverlayConfig(BaseModel):
    """Configuration for video overlay position and appearance"""
    
    x: int = Field(default=10, ge=0, description="X position in pixels")
    y: int = Field(default=10, ge=0, description="Y position in pixels")
    width: Optional[int] = Field(default=None, gt=0, description="Width in pixels")
    height: Optional[int] = Field(default=None, gt=0, description="Height in pixels")
    scale: float = Field(default=0.2, gt=0, le=1, description="Scale factor (0.0-1.0)")
    opacity: float = Field(default=1.0, ge=0, le=1, description="Opacity (0.0-1.0)")
    shape: OverlayShapeType = Field(default=OverlayShapeType.RECTANGLE, description="Shape type")
    border_radius: int = Field(default=0, ge=0, description="Border radius for rounded shape")
    
    @field_validator('border_radius')
    @classmethod
    def validate_border_radius(cls, v: int, info) -> int:
        """Border radius is only valid for rounded shape"""
        if 'shape' in info.data and info.data['shape'] == OverlayShapeType.ROUNDED:
            return v
        if v > 0:
            raise ValueError("border_radius is only valid for rounded shape")
        return v


class BorderStyle(BaseModel):
    """Border style configuration for overlay"""
    
    enabled: bool = Field(default=False, description="Enable border")
    width: int = Field(default=2, ge=0, description="Border width in pixels")
    color: str = Field(default="black", pattern=r"^#[0-9A-Fa-f]{6}$", description="Border color in hex format (#RRGGBB)")


class ShadowStyle(BaseModel):
    """Shadow style configuration for overlay"""
    
    enabled: bool = Field(default=False, description="Enable shadow")
    offset_x: int = Field(default=2, ge=-50, le=50, description="Shadow X offset in pixels")
    offset_y: int = Field(default=2, ge=-50, le=50, description="Shadow Y offset in pixels")
    blur: int = Field(default=2, ge=0, le=20, description="Shadow blur radius")
    color: str = Field(default="black", pattern=r"^#[0-9A-Fa-f]{6}$", description="Shadow color in hex format (#RRGGBB)")


class VideoOverlayRequest(BaseModel):
    """Request body for video overlay task"""
    
    base_video_file_id: FileSource = Field(..., description="ID or URL of the base video file")
    overlay_video_file_id: FileSource = Field(..., description="ID or URL of the overlay video file")
    config: OverlayConfig = Field(default_factory=OverlayConfig, description="Overlay configuration")
    border: BorderStyle = Field(default_factory=BorderStyle, description="Border style")
    shadow: ShadowStyle = Field(default_factory=ShadowStyle, description="Shadow style")
    output_filename: Optional[str] = Field(default=None, description="Output filename")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Celery task"""
        return {
            "base_video_file_id": self.base_video_file_id,
            "overlay_video_file_id": self.overlay_video_file_id,
            "config": self.config.model_dump(),
            "border": self.border.model_dump(),
            "shadow": self.shadow.model_dump(),
            "output_filename": self.output_filename,
        }
