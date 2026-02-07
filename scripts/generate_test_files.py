#!/usr/bin/env python3
"""
Generate test media files for load testing.

This script creates small, valid test video and audio files
that can be used for load testing the FFmpeg API.

Requires FFmpeg to be installed on the system.
"""

import os
import subprocess
import sys
from pathlib import Path


def generate_test_video(output_path: str, duration: int = 5, size: str = "320x240"):
    """
    Generate a test video file using FFmpeg.

    Args:
        output_path: Path where the video file will be saved
        duration: Duration of the video in seconds
        size: Resolution of the video (e.g., "320x240", "640x480")
    """
    try:
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"testsrc=duration={duration}:size={size}:rate=30",
            "-c:v", "libx264",
            "-t", str(duration),
            "-preset", "ultrafast",  # Fast encoding
            "-crf", "23",  # Good quality/size balance
            "-y",  # Overwrite if exists
            output_path
        ]
        
        print(f"Generating test video: {output_path}")
        print(f"Duration: {duration}s, Size: {size}")
        print(f"Command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        file_size = os.path.getsize(output_path)
        print(f"✓ Test video generated successfully: {output_path} ({file_size:,} bytes)")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error generating test video: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False
    except FileNotFoundError:
        print("✗ FFmpeg not found. Please install FFmpeg first.")
        print("  Ubuntu/Debian: sudo apt-get install ffmpeg")
        print("  macOS: brew install ffmpeg")
        print("  Windows: Download from https://ffmpeg.org/download.html")
        return False


def generate_test_audio(output_path: str, duration: int = 5, frequency: int = 1000):
    """
    Generate a test audio file using FFmpeg.

    Args:
        output_path: Path where the audio file will be saved
        duration: Duration of the audio in seconds
        frequency: Frequency of the sine wave in Hz
    """
    try:
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"sine=frequency={frequency}:duration={duration}",
            "-c:a", "libmp3lame",
            "-b:a", "128k",
            "-t", str(duration),
            "-y",
            output_path
        ]
        
        print(f"Generating test audio: {output_path}")
        print(f"Duration: {duration}s, Frequency: {frequency}Hz")
        print(f"Command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        file_size = os.path.getsize(output_path)
        print(f"✓ Test audio generated successfully: {output_path} ({file_size:,} bytes)")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error generating test audio: {e}")
        print(f"STDOUT: {e.stdout}")
        print(f"STDERR: {e.stderr}")
        return False
    except FileNotFoundError:
        print("✗ FFmpeg not found. Please install FFmpeg first.")
        return False


def generate_test_subtitle(output_path: str):
    """
    Generate a simple SRT subtitle file.

    Args:
        output_path: Path where the subtitle file will be saved
    """
    try:
        subtitle_content = """1
00:00:00,000 --> 00:00:02,000
Test subtitle line 1

2
00:00:02,000 --> 00:00:04,000
Test subtitle line 2

3
00:00:04,000 --> 00:00:05,000
End of test subtitles
"""
        
        with open(output_path, "w") as f:
            f.write(subtitle_content)
        
        file_size = os.path.getsize(output_path)
        print(f"✓ Test subtitle generated successfully: {output_path} ({file_size:,} bytes)")
        return True
        
    except Exception as e:
        print(f"✗ Error generating test subtitle: {e}")
        return False


def main():
    """Main function to generate all test files."""
    print("=" * 80)
    print("Test Media File Generator for FFmpeg API Load Testing")
    print("=" * 80)
    print()
    
    # Get the fixtures directory
    fixtures_dir = Path(__file__).parent.parent / "tests" / "fixtures"
    
    # Create directory if it doesn't exist
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Output directory: {fixtures_dir}")
    print()
    
    # Check if FFmpeg is installed
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            check=True,
            capture_output=True,
            timeout=5
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        print("✗ FFmpeg not found or not working correctly.")
        print()
        print("Please install FFmpeg before running this script:")
        print("  Ubuntu/Debian: sudo apt-get install ffmpeg")
        print("  macOS: brew install ffmpeg")
        print("  Windows: Download from https://ffmpeg.org/download.html")
        print()
        return 1
    
    # Generate test files
    results = []
    
    # Generate video file
    video_path = fixtures_dir / "test_video.mp4"
    results.append(
        generate_test_video(
            str(video_path),
            duration=5,
            size="320x240"
        )
    )
    
    # Generate audio file
    audio_path = fixtures_dir / "test_audio.mp3"
    results.append(
        generate_test_audio(
            str(audio_path),
            duration=5,
            frequency=1000
        )
    )
    
    # Generate subtitle file
    subtitle_path = fixtures_dir / "test_subtitle.srt"
    results.append(
        generate_test_subtitle(str(subtitle_path))
    )
    
    # Summary
    print()
    print("=" * 80)
    print("GENERATION SUMMARY")
    print("=" * 80)
    
    if all(results):
        print("✓ All test files generated successfully!")
        print()
        print("Generated files:")
        for path in fixtures_dir.glob("*"):
            size = path.stat().st_size
            print(f"  - {path.name} ({size:,} bytes)")
        print()
        print("You can now run load tests with:")
        print("  cd tests/load")
        print("  locust -f locustfile.py --headless --users 100 --spawn-rate 10 --run-time 2m")
        return 0
    else:
        print("✗ Some test files failed to generate.")
        print("Please check the error messages above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
