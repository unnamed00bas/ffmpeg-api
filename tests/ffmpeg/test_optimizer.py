"""
Тесты оптимизации FFmpeg: FFmpegOptimizer, HardwareAccelerator.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.ffmpeg.commands import (
    FFmpegOptimizer,
    FFmpegPreset,
    FFmpegTune,
    HardwareAccelerator,
)


class TestFFmpegOptimizer:
    """Unit тесты FFmpegOptimizer."""

    def test_init_with_defaults(self):
        """Инициализация с параметрами по умолчанию."""
        optimizer = FFmpegOptimizer()
        assert optimizer.preset == FFmpegPreset.FAST
        assert optimizer.tune is None
        assert optimizer.crf is None
        assert optimizer.threads is None

    def test_init_with_params(self):
        """Инициализация с параметрами."""
        optimizer = FFmpegOptimizer(
            preset=FFmpegPreset.MEDIUM,
            tune=FFmpegTune.FILM,
            crf=18,
            threads=4,
        )
        assert optimizer.preset == FFmpegPreset.MEDIUM
        assert optimizer.tune == FFmpegTune.FILM
        assert optimizer.crf == 18
        assert optimizer.threads == 4

    def test_get_encoding_params_includes_preset(self):
        """get_encoding_params включает preset."""
        optimizer = FFmpegOptimizer(preset=FFmpegPreset.VERYFAST)
        params = optimizer.get_encoding_params()
        assert "-preset" in params
        idx = params.index("-preset") + 1
        assert params[idx] == "veryfast"

    def test_get_encoding_params_includes_tune(self):
        """get_encoding_params включает tune."""
        optimizer = FFmpegOptimizer(tune=FFmpegTune.FASTDECODE)
        params = optimizer.get_encoding_params()
        assert "-tune" in params
        idx = params.index("-tune") + 1
        assert params[idx] == "fastdecode"

    def test_get_encoding_params_includes_crf(self):
        """get_encoding_params включает CRF."""
        optimizer = FFmpegOptimizer(crf=23)
        params = optimizer.get_encoding_params()
        assert "-crf" in params
        idx = params.index("-crf") + 1
        assert params[idx] == "23"

    def test_get_encoding_params_includes_threads(self):
        """get_encoding_params включает threads."""
        optimizer = FFmpegOptimizer(threads=8)
        params = optimizer.get_encoding_params()
        assert "-threads" in params
        idx = params.index("-threads") + 1
        assert params[idx] == "8"

    def test_optimize_for_scenario_fast(self):
        """scenario 'fast' возвращает VeryFast preset."""
        optimizer = FFmpegOptimizer()
        opt = optimizer.optimize_for_scenario("fast")
        assert opt["preset"] == FFmpegPreset.VERYFAST
        assert opt["tune"] == FFmpegTune.FASTDECODE
        assert opt["threads"] == 4

    def test_optimize_for_scenario_balanced(self):
        """scenario 'balanced' возвращает Fast preset."""
        optimizer = FFmpegOptimizer()
        opt = optimizer.optimize_for_scenario("balanced")
        assert opt["preset"] == FFmpegPreset.FAST
        assert opt["tune"] == FFmpegTune.FILM
        assert opt["threads"] == 4

    def test_optimize_for_scenario_quality(self):
        """scenario 'quality' возвращает Medium preset + CRF 18."""
        optimizer = FFmpegOptimizer()
        opt = optimizer.optimize_for_scenario("quality")
        assert opt["preset"] == FFmpegPreset.MEDIUM
        assert opt["tune"] == FFmpegTune.FILM
        assert opt["crf"] == 18
        assert opt["threads"] == 4

    def test_optimize_for_scenario_unknown_defaults_to_balanced(self):
        """Неведомый сценарий возвращает balanced."""
        optimizer = FFmpegOptimizer()
        opt = optimizer.optimize_for_scenario("unknown")
        assert opt["preset"] == FFmpegPreset.FAST
        assert opt["tune"] == FFmpegTune.FILM
        assert opt["threads"] == 4


class TestHardwareAccelerator:
    """Unit тесты HardwareAccelerator."""

    @patch("subprocess.run")
    def test_detect_available_returns_nvenc_if_present(self, mock_run):
        """Возвращает 'nvenc' если nvidia-smi доступен."""
        mock_run.return_value = MagicMock(returncode=0, stdout="RTX 3060\n")
        result = HardwareAccelerator.detect_available()
        assert "nvenc" in result

    @patch("subprocess.run")
    def test_detect_available_returns_vaapi_if_present(self, mock_run):
        """Возвращает 'vaapi' если vainfo доступен."""
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=""),
            MagicMock(returncode=0, stdout=""),
        ]
        result = HardwareAccelerator.detect_available()
        assert "vaapi" in result

    @patch("subprocess.run")
    def test_detect_available_returns_qsv_if_ffmpeg_hwaccels_lists_qsv(self, mock_run):
        """Возвращает 'qsv' если ffmpeg -hwaccels содержит qsv."""
        mock_run.side_effect = [
            MagicMock(returncode=1),
            MagicMock(returncode=1),
            MagicMock(stdout="qsv"),
        ]
        result = HardwareAccelerator.detect_available()
        assert "qsv" in result

    @patch("subprocess.run")
    def test_detect_available_returns_empty_if_none(self, mock_run):
        """Возвращает пустой список если ничего нет."""
        mock_run.side_effect = [
            MagicMock(returncode=1),
            MagicMock(returncode=1),
            MagicMock(stdout=""),
        ]
        result = HardwareAccelerator.detect_available()
        assert result == []

    def test_get_hwaccel_params_nvenc(self):
        """get_hwaccel_params для nvenc."""
        params = HardwareAccelerator.get_hwaccel_params("nvenc")
        assert "-hwaccel" in params
        assert "-c:v" in params
        assert params[params.index("-c:v") + 1] == "h264_nvenc"

    def test_get_hwaccel_params_qsv(self):
        """get_hwaccel_params для qsv."""
        params = HardwareAccelerator.get_hwaccel_params("qsv")
        assert "-hwaccel" in params
        assert "-c:v" in params
        assert params[params.index("-c:v") + 1] == "h264_qsv"

    def test_get_hwaccel_params_vaapi(self):
        """get_hwaccel_params для vaapi."""
        params = HardwareAccelerator.get_hwaccel_params("vaapi")
        assert "-hwaccel" in params
        assert "-vaapi_device" in params
        assert "-c:v" in params
        assert "h264_vaapi" in params

    def test_get_hwaccel_params_unknown_returns_empty(self):
        """Неведомый ускоритель возвращает пустой список."""
        params = HardwareAccelerator.get_hwaccel_params("unknown")
        assert params == []
