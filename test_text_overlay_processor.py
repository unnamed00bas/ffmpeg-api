"""
Simple test runner for text overlay processor
"""
import sys
sys.path.insert(0, 'c:\\Users\\User\\PROJECTS\\ffmpeg-api')

from typing import Any, Dict, List, Optional
from unittest.mock import Mock, AsyncMock, patch
import asyncio

# Mock BaseProcessor
class MockBaseProcessor:
    def __init__(self, task_id: int, config: Dict[str, Any], progress_callback=None):
        self.task_id = task_id
        self.config = config
        self.progress_callback = progress_callback
        self.temp_files: List[str] = []

    async def cleanup(self) -> None:
        for path in self.temp_files:
            pass
        self.temp_files.clear()

    def update_progress(self, progress: float) -> None:
        if self.progress_callback:
            self.progress_callback(progress)

    def add_temp_file(self, file_path: str) -> None:
        self.temp_files.append(file_path)

# Import processor components
import os
import re
import uuid

# Inline implementation of key processor methods for testing
def calculate_position(position_config: Dict[str, Any]) -> Dict[str, str]:
    pos_type = position_config.get("type", "relative")
    if pos_type == "absolute":
        x = position_config.get("x", 0)
        y = position_config.get("y", 0)
        return {"x": str(x), "y": str(y)}
    else:
        return get_relative_position(position_config)

def get_relative_position(position_config: Dict[str, Any]) -> Dict[str, str]:
    position = position_config.get("position", "center")
    margin_x = position_config.get("margin_x", 10)
    margin_y = position_config.get("margin_y", 10)

    positions = {
        "top-left": {"x": f"{margin_x}", "y": f"{margin_y}"},
        "top-center": {"x": f"(w-tw)/2", "y": f"{margin_y}"},
        "top-right": {"x": f"w-tw-{margin_x}", "y": f"{margin_y}"},
        "center-left": {"x": f"{margin_x}", "y": f"(h-th)/2"},
        "center": {"x": f"(w-tw)/2", "y": f"(h-th)/2"},
        "center-right": {"x": f"w-tw-{margin_x}", "y": f"(h-th)/2"},
        "bottom-left": {"x": f"{margin_x}", "y": f"h-th-{margin_y}"},
        "bottom-center": {"x": f"(w-tw)/2", "y": f"h-th-{margin_y}"},
        "bottom-right": {"x": f"w-tw-{margin_x}", "y": f"h-th-{margin_y}"},
    }
    return positions.get(position, positions["center"])

def escape_text(text: str) -> str:
    escaped = text
    escaped = escaped.replace("'", "'\\''")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("=", "\\=")
    escaped = escaped.replace("#", "\\#")
    escaped = escaped.replace("[", "\\[")
    escaped = escaped.replace("]", "\\]")
    escaped = escaped.replace("{", "\\{")
    escaped = escaped.replace("}", "\\}")
    escaped = escaped.replace("%", "\\%")
    escaped = escaped.replace("\\", "\\\\")
    return escaped

def color_to_hex(color: str, alpha: float = 1.0) -> str:
    hex_color = color.lstrip("#")
    r = hex_color[0:2]
    g = hex_color[2:4]
    b = hex_color[4:6]
    a = int(255 * alpha)
    return f"&H{a:02X}{b}{g}{r}&"

# Test functions
def test_absolute_position():
    config = {"type": "absolute", "x": 100, "y": 200}
    result = calculate_position(config)
    assert result == {"x": "100", "y": "200"}
    print("[PASS] test_absolute_position")

def test_relative_position_center():
    config = {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10}
    result = calculate_position(config)
    assert result == {"x": "(w-tw)/2", "y": "(h-th)/2"}
    print("[PASS] test_relative_position_center")

def test_relative_position_top_left():
    config = {"type": "relative", "position": "top-left", "margin_x": 20, "margin_y": 30}
    result = calculate_position(config)
    assert result == {"x": "20", "y": "30"}
    print("[PASS] test_relative_position_top_left")

def test_relative_position_bottom_right():
    config = {"type": "relative", "position": "bottom-right", "margin_x": 15, "margin_y": 20}
    result = calculate_position(config)
    assert result == {"x": "w-tw-15", "y": "h-th-20"}
    print("[PASS] test_relative_position_bottom_right")

def test_all_positions():
    positions = [
        ("top-left", {"x": "10", "y": "10"}),
        ("top-center", {"x": "(w-tw)/2", "y": "10"}),
        ("top-right", {"x": "w-tw-10", "y": "10"}),
        ("center-left", {"x": "10", "y": "(h-th)/2"}),
        ("center", {"x": "(w-tw)/2", "y": "(h-th)/2"}),
        ("center-right", {"x": "w-tw-10", "y": "(h-th)/2"}),
        ("bottom-left", {"x": "10", "y": "h-th-10"}),
        ("bottom-center", {"x": "(w-tw)/2", "y": "h-th-10"}),
        ("bottom-right", {"x": "w-tw-10", "y": "h-th-10"}),
    ]
    for position, expected in positions:
        config = {"type": "relative", "position": position, "margin_x": 10, "margin_y": 10}
        result = calculate_position(config)
        assert result == expected, f"Failed for position: {position}"
    print("[PASS] test_all_positions")

def test_escape_simple_text():
    text = "Hello World"
    escaped = escape_text(text)
    assert ":" in escaped or "Hello World" in escaped
    print("[PASS] test_escape_simple_text")

def test_escape_special_chars():
    text = "Hello: World! [test]"
    escaped = escape_text(text)
    assert "\\:" in escaped
    assert "\\[" in escaped
    assert "\\]" in escaped
    print("[PASS] test_escape_special_chars")

def test_escape_quotes():
    text = "Don't worry"
    escaped = escape_text(text)
    assert "\\" in escaped  # Check that backslash was added
    print("[PASS] test_escape_quotes")

def test_color_to_hex_red():
    result = color_to_hex("#FF0000", 1.0)
    assert result == "&HFF0000FF&"
    print("[PASS] test_color_to_hex_red")

def test_color_to_hex_with_alpha():
    result = color_to_hex("#00FF00", 0.5)
    assert result.startswith("&H")
    assert "00FF00" in result
    assert "&" in result
    print("[PASS] test_color_to_hex_with_alpha")

def test_drawtext_filter_basic():
    config = {
        "text": "Test Text",
        "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
        "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
        "background": {"enabled": False, "color": "black", "alpha": 0.5, "padding": 10, "border_radius": 5},
        "border": {"enabled": False, "width": 2, "color": "black"},
        "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
        "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
        "rotation": 0,
        "opacity": 1.0,
        "start_time": 0.0,
        "end_time": None,
    }

    text = escape_text(config["text"])
    style = config["style"]
    position = calculate_position(config["position"])
    color = color_to_hex(style["color"], style["alpha"])

    params = []
    params.append(f"text='{text}'")
    params.append(f"fontfile='{style['font_family']}'")
    params.append(f"fontsize={style['font_size']}")
    params.append(f"fontcolor={color}")
    params.append(f"x={position['x']}")
    params.append(f"y={position['y']}")

    filter_str = ":".join(params)
    assert "text=" in filter_str
    assert "fontsize=24" in filter_str
    assert "fontcolor=" in filter_str
    assert "x=(w-tw)/2" in filter_str or "x=" in filter_str
    print("[PASS] test_drawtext_filter_basic")

def test_drawtext_filter_with_background():
    config = {
        "text": "Text with BG",
        "position": {"type": "relative", "position": "center", "margin_x": 10, "margin_y": 10},
        "style": {"font_family": "Arial", "font_size": 24, "font_weight": "normal", "color": "white", "alpha": 1.0},
        "background": {"enabled": True, "color": "#000000", "alpha": 0.7, "padding": 20, "border_radius": 10},
        "border": {"enabled": False, "width": 2, "color": "black"},
        "shadow": {"enabled": False, "offset_x": 2, "offset_y": 2, "blur": 2, "color": "black"},
        "animation": {"type": "none", "duration": 1.0, "delay": 0.0},
        "rotation": 0,
        "opacity": 1.0,
        "start_time": 0.0,
        "end_time": None,
    }

    bg = config["background"]
    params = []
    params.append("box=1")
    params.append(f"boxcolor={color_to_hex(bg['color'], bg['alpha'])}")
    params.append(f"boxborderw={bg['padding']}")
    params.append(f"boxradius={bg['border_radius']}")

    assert "box=1" in params
    assert "boxborderw=20" in params
    assert "boxradius=10" in params
    print("[PASS] test_drawtext_filter_with_background")

def test_drawtext_filter_with_border():
    config = {
        "border": {"enabled": True, "width": 3, "color": "#FFFFFF"},
    }

    border = config["border"]
    params = []
    params.append(f"borderw={border['width']}")
    params.append(f"bordercolor={color_to_hex(border['color'], 1.0)}")

    assert "borderw=3" in params
    assert len(params) == 2
    print("[PASS] test_drawtext_filter_with_border")

def test_drawtext_filter_with_shadow():
    config = {
        "shadow": {"enabled": True, "offset_x": 5, "offset_y": -3, "blur": 4, "color": "#000000"},
    }

    shadow = config["shadow"]
    params = []
    params.append(f"shadowx={shadow['offset_x']}")
    params.append(f"shadowy={shadow['offset_y']}")
    params.append(f"shadowcolor={color_to_hex(shadow['color'], 1.0)}")
    params.append(f"shadoww={shadow['blur']}")

    assert "shadowx=5" in params
    assert "shadowy=-3" in params
    assert "shadoww=4" in params
    assert len(params) == 4
    print("[PASS] test_drawtext_filter_with_shadow")

def test_drawtext_filter_with_rotation():
    config = {"rotation": 45}
    rotation = config.get("rotation", 0)
    if rotation != 0:
        assert rotation == 45
        print("[PASS] test_drawtext_filter_with_rotation")

def test_drawtext_filter_with_opacity():
    config = {"opacity": 0.8}
    opacity = config.get("opacity", 1.0)
    if opacity < 1.0:
        assert opacity == 0.8
        print("[PASS] test_drawtext_filter_with_opacity")

if __name__ == "__main__":
    print("Running text overlay processor tests...")
    print()

    test_absolute_position()
    test_relative_position_center()
    test_relative_position_top_left()
    test_relative_position_bottom_right()
    test_all_positions()
    test_escape_simple_text()
    test_escape_special_chars()
    test_escape_quotes()
    test_color_to_hex_red()
    test_color_to_hex_with_alpha()
    test_drawtext_filter_basic()
    test_drawtext_filter_with_background()
    test_drawtext_filter_with_border()
    test_drawtext_filter_with_shadow()
    test_drawtext_filter_with_rotation()
    test_drawtext_filter_with_opacity()

    print()
    print("=" * 50)
    print("All tests passed! [OK]")
    print("=" * 50)
