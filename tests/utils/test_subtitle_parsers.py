"""
Tests for subtitle parsers
"""
import pytest

from app.utils.subtitle_parsers import (
    parse_srt,
    _parse_srt_time,
    parse_vtt,
    _parse_vtt_time,
    parse_ass,
    _parse_ass_time,
    parse_ssa,
)


class TestSrtParser:
    """Tests for SRT format parser"""

    def test_parse_correct_srt(self):
        """Test parsing correct SRT format"""
        content = """1
00:00:01,000 --> 00:00:04,000
Hello World

2
00:00:05,500 --> 00:00:08,000
Second subtitle
with two lines"""

        result = parse_srt(content)

        assert len(result) == 2
        assert result[0]["index"] == 1
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 4.0
        assert result[0]["text"] == "Hello World"

        assert result[1]["index"] == 2
        assert result[1]["start"] == 5.5
        assert result[1]["end"] == 8.0
        assert result[1]["text"] == "Second subtitle\nwith two lines"

    def test_parse_srt_times(self):
        """Test time parsing in SRT format"""
        content = """1
00:01:30,500 --> 00:02:15,750
Time test"""

        result = parse_srt(content)

        # 1:30:500 = 90.5 seconds
        assert result[0]["start"] == 90.5
        # 2:15:750 = 135.75 seconds
        assert result[0]["end"] == 135.75

    def test_parse_srt_text(self):
        """Test text extraction from SRT"""
        content = """1
00:00:01,000 --> 00:00:04,000
Text with <i>tags</i> and {"special": "chars"}

2
00:00:05,000 --> 00:00:08,000
Another text"""

        result = parse_srt(content)

        assert "<i>tags</i>" in result[0]["text"]
        assert '{"special": "chars"}' in result[0]["text"]
        assert result[1]["text"] == "Another text"

    def test_parse_srt_invalid_format(self):
        """Test that invalid SRT format raises exception"""
        content = """Invalid
Format
Without time"""

        with pytest.raises(ValueError, match="Invalid time format"):
            parse_srt(content)

    def test_parse_srt_empty_content(self):
        """Test parsing empty SRT content"""
        result = parse_srt("")
        assert result == []

    def test_parse_srt_time_function(self):
        """Test _parse_srt_time helper function"""
        assert _parse_srt_time("00:00:01,000") == 1.0
        assert _parse_srt_time("00:00:10,500") == 10.5
        assert _parse_srt_time("01:00:00,000") == 3600.0
        assert _parse_srt_time("01:30:45,250") == 5445.25

    def test_parse_srt_time_invalid(self):
        """Test that invalid time format raises exception"""
        with pytest.raises(ValueError, match="Invalid SRT time format"):
            _parse_srt_time("invalid")


class TestVttParser:
    """Tests for WebVTT format parser"""

    def test_parse_correct_vtt(self):
        """Test parsing correct WebVTT format"""
        content = """WEBVTT

00:00:01.000 --> 00:00:04.000
Hello World

00:00:05.500 --> 00:00:08.000
Second subtitle"""

        result = parse_vtt(content)

        assert len(result) == 2
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 4.0
        assert result[0]["text"] == "Hello World"

        assert result[1]["start"] == 5.5
        assert result[1]["end"] == 8.0
        assert result[1]["text"] == "Second subtitle"

    def test_parse_vtt_times(self):
        """Test time parsing in WebVTT format"""
        content = """WEBVTT

00:01:30.500 --> 00:02:15.750
Time test"""

        result = parse_vtt(content)

        assert result[0]["start"] == 90.5
        assert result[0]["end"] == 135.75

    def test_parse_vtt_ignores_header(self):
        """Test that WEBVTT header is ignored"""
        content = """WEBVTT

00:00:01.000 --> 00:00:04.000
Content"""

        result = parse_vtt(content)
        assert len(result) == 1
        assert "WEBVTT" not in result[0]["text"]

    def test_parse_vtt_with_settings(self):
        """Test parsing VTT with settings lines"""
        content = """WEBVTT
NOTE This is a comment

00:00:01.000 --> 00:00:04.000
Subtitle 1

STYLE
::cue { color: white; }

00:00:05.000 --> 00:00:08.000
Subtitle 2"""

        result = parse_vtt(content)

        assert len(result) == 2
        assert result[0]["text"] == "Subtitle 1"
        assert result[1]["text"] == "Subtitle 2"

    def test_parse_vtt_empty_content(self):
        """Test parsing empty VTT content"""
        result = parse_vtt("")
        assert result == []

    def test_parse_vtt_time_function(self):
        """Test _parse_vtt_time helper function"""
        assert _parse_vtt_time("00:00:01.000") == 1.0
        assert _parse_vtt_time("00:00:10.500") == 10.5
        assert _parse_vtt_time("01:00:00.000") == 3600.0
        assert _parse_vtt_time("01:30:45.250") == 5445.25

    def test_parse_vtt_time_invalid(self):
        """Test that invalid time format raises exception"""
        with pytest.raises(ValueError, match="Invalid VTT time format"):
            _parse_vtt_time("invalid")


class TestAssParser:
    """Tests for ASS format parser"""

    def test_parse_correct_ass(self):
        """Test parsing correct ASS format"""
        content = """[Script Info]
Title: Test

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100.0,100.0,0.0,0.0,1,2.0,2.0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello World
Dialogue: 0,0:00:05.50,0:00:08.00,Default,,0,0,0,,Second subtitle"""

        result = parse_ass(content)

        assert len(result) == 2
        assert result[0]["layer"] == 0
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 4.0
        assert result[0]["style"] == "Default"
        assert result[0]["text"] == "Hello World"

        assert result[1]["start"] == 5.5
        assert result[1]["end"] == 8.0
        assert result[1]["text"] == "Second subtitle"

    def test_parse_ass_with_tags(self):
        """Test parsing ASS with text tags"""
        content = """[Script Info]

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100.0,100.0,0.0,0.0,1,2.0,2.0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,{\\b1}{\\i1}Bold italic{\\b0}{\\i0}"""

        result = parse_ass(content)

        assert result[0]["text"] == "{\\b1}{\\i1}Bold italic{\\b0}{\\i0}"

    def test_parse_ass_margins(self):
        """Test parsing ASS margin values"""
        content = """[Script Info]

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100.0,100.0,0.0,0.0,1,2.0,2.0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,20,30,40,,Test"""

        result = parse_ass(content)

        assert result[0]["margin_l"] == 20
        assert result[0]["margin_r"] == 30
        assert result[0]["margin_v"] == 40

    def test_parse_ass_empty_content(self):
        """Test parsing empty ASS content"""
        result = parse_ass("")
        assert result == []

    def test_parse_ass_only_header(self):
        """Test parsing ASS with only header sections"""
        content = """[Script Info]
Title: Test

[V4+ Styles]
Format: Name, Fontname, Fontsize
Style: Default,Arial,20"""

        result = parse_ass(content)
        assert result == []

    def test_parse_ass_time_function(self):
        """Test _parse_ass_time helper function"""
        assert _parse_ass_time("0:00:01.00") == 1.0
        assert _parse_ass_time("0:00:10.50") == 10.5
        assert _parse_ass_time("1:00:00.00") == 3600.0
        assert _parse_ass_time("1:30:45.25") == 5445.25

    def test_parse_ass_time_invalid(self):
        """Test that invalid time format raises exception"""
        with pytest.raises(ValueError, match="Invalid ASS time format"):
            _parse_ass_time("invalid")


class TestSsaParser:
    """Tests for SSA format parser"""

    def test_parse_correct_ssa(self):
        """Test parsing correct SSA format (similar to ASS)"""
        content = """[Script Info]
Title: Test

[V4 Styles]
Format: Name, Fontname, Fontsize
Style: Default,Arial,20

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello World"""

        result = parse_ssa(content)

        assert len(result) == 1
        assert result[0]["layer"] == 0
        assert result[0]["start"] == 1.0
        assert result[0]["end"] == 4.0
        assert result[0]["text"] == "Hello World"

    def test_parse_ssa_same_as_ass(self):
        """Test that SSA parser uses the same logic as ASS"""
        ass_content = """[Script Info]
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Test"""

        ssa_content = """[Script Info]
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Test"""

        ass_result = parse_ass(ass_content)
        ssa_result = parse_ssa(ssa_content)

        assert ass_result == ssa_result
