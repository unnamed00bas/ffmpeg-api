"""
FFmpeg/ffprobe command execution
"""
import asyncio
import json
import re
import subprocess
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.config import get_settings
from app.ffmpeg.exceptions import (
    FFmpegProcessingError,
    FFmpegTimeoutError,
)
from app.ffmpeg.utils import parse_duration, parse_ffmpeg_output

settings = get_settings()
FFMPEG_PATH = getattr(settings, "FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = getattr(settings, "FFPROBE_PATH", "ffprobe")


class FFmpegPreset(str, Enum):
    """FFmpeg encoding presets (x264/x265)."""
    ULTRAFAST = "ultrafast"
    SUPERFAST = "superfast"
    VERYFAST = "veryfast"
    FASTER = "faster"
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    SLOWER = "slower"
    VERYSLOW = "veryslow"


class FFmpegTune(str, Enum):
    """FFmpeg tuning parameters."""
    FILM = "film"
    ANIMATION = "animation"
    GRAIN = "grain"
    STILLIMAGE = "stillimage"
    FASTDECODE = "fastdecode"
    ZEROLATENCY = "zerolatency"


class FFmpegOptimizer:
    """Оптимизация параметров кодирования FFmpeg."""

    def __init__(
        self,
        preset: FFmpegPreset = FFmpegPreset.FAST,
        tune: Optional[FFmpegTune] = None,
        crf: Optional[int] = None,
        threads: Optional[int] = None,
    ):
        self.preset = preset
        self.tune = tune
        self.crf = crf
        self.threads = threads

    def get_encoding_params(self) -> List[str]:
        """Возвращает список аргументов для кодирования (x264)."""
        params: List[str] = []
        params.extend(["-preset", self.preset.value])
        if self.tune:
            params.extend(["-tune", self.tune.value])
        if self.crf is not None:
            params.extend(["-crf", str(self.crf)])
        if self.threads:
            params.extend(["-threads", str(self.threads)])
        return params

    def optimize_for_scenario(self, scenario: str) -> Dict[str, Any]:
        """Рекомендуемые настройки для сценария: fast, balanced, quality."""
        scenarios: Dict[str, Dict[str, Any]] = {
            "fast": {
                "preset": FFmpegPreset.VERYFAST,
                "tune": FFmpegTune.FASTDECODE,
                "threads": 4,
            },
            "balanced": {
                "preset": FFmpegPreset.FAST,
                "tune": FFmpegTune.FILM,
                "threads": 4,
            },
            "quality": {
                "preset": FFmpegPreset.MEDIUM,
                "tune": FFmpegTune.FILM,
                "crf": 18,
                "threads": 4,
            },
        }
        return scenarios.get(scenario, scenarios["balanced"])


class HardwareAccelerator:
    """Обнаружение и параметры аппаратного ускорения."""

    @staticmethod
    def detect_available() -> List[str]:
        """Проверка доступного hardware acceleration (nvenc, qsv, vaapi)."""
        available: List[str] = []
        # NVENC (NVIDIA)
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                available.append("nvenc")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        # QSV / VAAPI (vainfo часто доступен на Linux с Intel/AMD)
        try:
            result = subprocess.run(
                ["vainfo"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                available.append("vaapi")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        # QSV (Intel) — отдельная проверка через ffmpeg -hwaccels или оставляем только vaapi
        try:
            result = subprocess.run(
                [FFMPEG_PATH, "-hide_banner", "-hwaccels"],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0 and b"qsv" in (result.stderr or b""):
                if "qsv" not in available:
                    available.append("qsv")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return available

    @staticmethod
    def get_hwaccel_params(accelerator: str) -> List[str]:
        """Параметры FFmpeg для выбранного ускорителя."""
        if accelerator == "nvenc":
            return ["-hwaccel", "cuda", "-c:v", "h264_nvenc"]
        if accelerator == "qsv":
            return ["-hwaccel", "qsv", "-c:v", "h264_qsv"]
        if accelerator == "vaapi":
            return [
                "-hwaccel", "vaapi",
                "-vaapi_device", "/dev/dri/renderD128",
                "-c:v", "h264_vaapi",
            ]
        return []


class FFmpegCommand:
    """Запуск FFmpeg/ffprobe и разбор вывода."""

    @staticmethod
    async def run_command(
        command: List[str],
        timeout: int = 3600,
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> str:
        """
        Запуск команды (ffmpeg/ffprobe) с таймаутом и опциональным прогрессом.

        Args:
            command: Список аргументов (например ["ffmpeg", "-i", "in.mp4", "out.mp4"])
            timeout: Таймаут в секундах
            progress_callback: Вызывается с прогрессом 0.0–100.0 по мере вывода stderr

        Returns:
            stdout команды

        Raises:
            FFmpegTimeoutError: при таймауте
            FFmpegProcessingError: при ненулевом коде возврата
        """
        proc = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_chunks: List[bytes] = []
        stderr_chunks: List[bytes] = []

        async def read_stdout():
            if proc.stdout:
                while True:
                    chunk = await proc.stdout.read(8192)
                    if not chunk:
                        break
                    stdout_chunks.append(chunk)

        async def read_stderr():
            if proc.stderr:
                while True:
                    chunk = await proc.stderr.read(8192)
                    if not chunk:
                        break
                    stderr_chunks.append(chunk)
                    if progress_callback:
                        text = chunk.decode("utf-8", errors="replace")
                        p = FFmpegCommand.parse_ffmpeg_progress(text)
                        if p is not None:
                            progress_callback(p)

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    read_stdout(),
                    read_stderr(),
                    proc.wait(),
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise FFmpegTimeoutError(f"Command timed out after {timeout}s")

        stderr = b"".join(stderr_chunks).decode("utf-8", errors="replace")
        if proc.returncode != 0:
            raise FFmpegProcessingError(
                f"FFmpeg exited with code {proc.returncode}: {stderr[-2000:]}"
            )
        return b"".join(stdout_chunks).decode("utf-8", errors="replace")

    @staticmethod
    async def get_video_info(file_path: str) -> Dict[str, Any]:
        """
        Информация о видео через ffprobe (JSON).

        Returns:
            Словарь с streams[].width, height, duration, codec_name и т.д.
        """
        cmd = [
            FFPROBE_PATH,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        out = await FFmpegCommand.run_command(cmd, timeout=30)
        data = json.loads(out)
        result: Dict[str, Any] = {
            "duration": 0.0,
            "width": None,
            "height": None,
            "video_codec": None,
            "fps": None,
        }
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                result["width"] = int(stream.get("width", 0))
                result["height"] = int(stream.get("height", 0))
                result["video_codec"] = stream.get("codec_name")
                if "r_frame_rate" in stream:
                    num, den = stream["r_frame_rate"].split("/")
                    if int(den):
                        result["fps"] = float(num) / int(den)
                break
        fmt = data.get("format", {})
        if "duration" in fmt:
            result["duration"] = float(fmt["duration"])
        return result

    @staticmethod
    async def get_audio_info(file_path: str) -> Dict[str, Any]:
        """Информация об аудио через ffprobe."""
        cmd = [
            FFPROBE_PATH,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]
        out = await FFmpegCommand.run_command(cmd, timeout=30)
        data = json.loads(out)
        result: Dict[str, Any] = {
            "duration": 0.0,
            "audio_codec": None,
            "bitrate": None,
        }
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "audio":
                result["audio_codec"] = stream.get("codec_name")
                break
        fmt = data.get("format", {})
        result["duration"] = float(fmt.get("duration", 0))
        result["bitrate"] = int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None
        return result

    @staticmethod
    async def validate_file(file_path: str) -> bool:
        """Проверка файла через ffprobe (доступен и не повреждён)."""
        try:
            await FFmpegCommand.get_video_info(file_path)
            return True
        except Exception:
            try:
                await FFmpegCommand.get_audio_info(file_path)
                return True
            except Exception:
                return False

    @staticmethod
    def parse_ffmpeg_progress(
        stderr: str, total_duration: Optional[float] = None
    ) -> Optional[float]:
        """
        Парсинг прогресса из stderr FFmpeg (time=00:01:23.45).

        Args:
            stderr: Вывод stderr (фрагмент или полный)
            total_duration: Общая длительность в секундах; если задана, возвращается 0–100

        Returns:
            Прогресс: 0.0–100.0 при заданном total_duration, иначе текущее время в секундах или None
        """
        m = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", stderr)
        if not m:
            return None
        current = parse_duration(m.group(1))
        if total_duration and total_duration > 0:
            return min(100.0, max(0.0, 100.0 * current / total_duration))
        return current