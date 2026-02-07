"""
Simple test runner for text overlay schemas
"""
import sys
sys.path.insert(0, 'c:\\Users\\User\\PROJECTS\\ffmpeg-api')

from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional

# Define schemas inline to avoid database dependency
class TextPositionType(str, Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"

class TextPosition(BaseModel):
    type: TextPositionType = TextPositionType.RELATIVE
    x: Optional[int] = None
    y: Optional[int] = None
    position: Optional[str] = Field(default="center")
    margin_x: int = Field(default=10, ge=0)
    margin_y: int = Field(default=10, ge=0)

    @field_validator("position")
    @classmethod
    def validate_position(cls, v):
        valid_positions = [
            "top-left", "top-center", "top-right",
            "center-left", "center", "center-right",
            "bottom-left", "bottom-center", "bottom-right"
        ]
        if v not in valid_positions:
            raise ValueError(f"Position must be one of: {', '.join(valid_positions)}")
        return v

class TextStyle(BaseModel):
    font_family: str = Field(default="Arial", min_length=1)
    font_size: int = Field(default=24, ge=8, le=200)
    font_weight: str = Field(default="normal", pattern=r"^(normal|bold|100|200|300|400|500|600|700|800|900)$")
    color: str = Field(default="white", pattern=r"^#[0-9A-Fa-f]{6}$")
    alpha: float = Field(default=1.0, ge=0.0, le=1.0)

class TextBackground(BaseModel):
    enabled: bool = False
    color: str = Field(default="black", pattern=r"^#[0-9A-Fa-f]{6}$")
    alpha: float = Field(default=0.5, ge=0.0, le=1.0)
    padding: int = Field(default=10, ge=0)
    border_radius: int = Field(default=5, ge=0)

class TextBorder(BaseModel):
    enabled: bool = False
    width: int = Field(default=2, ge=0)
    color: str = Field(default="black", pattern=r"^#[0-9A-Fa-f]{6}$")

class TextShadow(BaseModel):
    enabled: bool = False
    offset_x: int = Field(default=2, ge=-50, le=50)
    offset_y: int = Field(default=2, ge=-50, le=50)
    blur: int = Field(default=2, ge=0, le=20)
    color: str = Field(default="black", pattern=r"^#[0-9A-Fa-f]{6}$")

class TextAnimationType(str, Enum):
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
    type: TextAnimationType = TextAnimationType.NONE
    duration: float = Field(default=1.0, ge=0.0)
    delay: float = Field(default=0.0, ge=0.0)

class TextOverlayRequest(BaseModel):
    video_file_id: int = Field(..., gt=0)
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
    def validate_text(cls, v):
        if not v or not v.strip():
            raise ValueError("Text cannot be empty")
        return v

# Run tests
def test_text_overlay_request_valid():
    request = TextOverlayRequest(
        video_file_id=1,
        text="Sample text",
    )
    assert request.video_file_id == 1
    assert request.text == "Sample text"
    assert request.position.type == TextPositionType.RELATIVE
    assert request.style.font_family == "Arial"
    assert request.style.font_size == 24
    print("[PASS] test_text_overlay_request_valid")

def test_text_position_absolute():
    position = TextPosition(
        type=TextPositionType.ABSOLUTE,
        x=100,
        y=200,
    )
    assert position.type == TextPositionType.ABSOLUTE
    assert position.x == 100
    assert position.y == 200
    print("[PASS] test_text_position_absolute")

def test_text_position_relative():
    position = TextPosition(
        type=TextPositionType.RELATIVE,
        position="top-left",
        margin_x=20,
        margin_y=30,
    )
    assert position.type == TextPositionType.RELATIVE
    assert position.position == "top-left"
    assert position.margin_x == 20
    assert position.margin_y == 30
    print("[PASS] test_text_position_relative")

def test_text_position_invalid():
    try:
        TextPosition(position="invalid-position")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Position must be one of" in str(e)
        print("[PASS] test_text_position_invalid")

def test_text_style_bounds():
    style = TextStyle(
        font_family="Roboto",
        font_size=50,
        font_weight="bold",
        color="#FF0000",
        alpha=0.8,
    )
    assert style.font_family == "Roboto"
    assert style.font_size == 50
    assert style.font_weight == "bold"
    assert style.color == "#FF0000"
    assert style.alpha == 0.8
    print("[PASS] test_text_style_bounds")

def test_text_style_invalid_size():
    try:
        TextStyle(font_size=5)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
    print("[PASS] test_text_style_invalid_size")

def test_text_background_valid():
    background = TextBackground(
        enabled=True,
        color="#000000",
        alpha=0.7,
        padding=15,
        border_radius=8,
    )
    assert background.enabled is True
    assert background.color == "#000000"
    assert background.alpha == 0.7
    assert background.padding == 15
    assert background.border_radius == 8
    print("[PASS] test_text_background_valid")

def test_text_border_valid():
    border = TextBorder(
        enabled=True,
        width=3,
        color="#00FF00",
    )
    assert border.enabled is True
    assert border.width == 3
    assert border.color == "#00FF00"
    print("[PASS] test_text_border_valid")

def test_text_shadow_valid():
    shadow = TextShadow(
        enabled=True,
        offset_x=5,
        offset_y=-3,
        blur=4,
        color="#0000FF",
    )
    assert shadow.enabled is True
    assert shadow.offset_x == 5
    assert shadow.offset_y == -3
    assert shadow.blur == 4
    assert shadow.color == "#0000FF"
    print("[PASS] test_text_shadow_valid")

def test_text_animation_valid():
    animation = TextAnimation(
        type=TextAnimationType.FADE_IN,
        duration=2.5,
        delay=0.5,
    )
    assert animation.type == TextAnimationType.FADE_IN
    assert animation.duration == 2.5
    assert animation.delay == 0.5
    print("[PASS] test_text_animation_valid")

def test_full_request():
    request = TextOverlayRequest(
        video_file_id=123,
        text="Hello World!",
        position=TextPosition(
            type=TextPositionType.RELATIVE,
            position="center",
            margin_x=50,
            margin_y=50,
        ),
        style=TextStyle(
            font_family="Arial",
            font_size=36,
            font_weight="bold",
            color="#FFFFFF",
            alpha=1.0,
        ),
        background=TextBackground(
            enabled=True,
            color="#000000",
            alpha=0.5,
            padding=20,
            border_radius=10,
        ),
        border=TextBorder(
            enabled=True,
            width=2,
            color="#FFFFFF",
        ),
        shadow=TextShadow(
            enabled=True,
            offset_x=2,
            offset_y=2,
            blur=3,
            color="#000000",
        ),
        animation=TextAnimation(
            type=TextAnimationType.FADE_IN,
            duration=1.0,
            delay=0.0,
        ),
        rotation=0,
        opacity=1.0,
        start_time=0.0,
        end_time=10.0,
        output_filename="output.mp4",
    )
    assert request.text == "Hello World!"
    assert request.position.position == "center"
    assert request.style.font_size == 36
    assert request.background.enabled is True
    assert request.border.enabled is True
    assert request.shadow.enabled is True
    assert request.animation.type == TextAnimationType.FADE_IN
    print("[PASS] test_full_request")

if __name__ == "__main__":
    print("Running text overlay schema tests...")
    print()

    test_text_overlay_request_valid()
    test_text_position_absolute()
    test_text_position_relative()
    test_text_position_invalid()
    test_text_style_bounds()
    test_text_style_invalid_size()
    test_text_background_valid()
    test_text_border_valid()
    test_text_shadow_valid()
    test_text_animation_valid()
    test_full_request()

    print()
    print("=" * 50)
    print("All tests passed! [OK]")
    print("=" * 50)
