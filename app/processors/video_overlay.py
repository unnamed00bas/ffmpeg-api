"""
Video overlay processor for Picture-in-Picture functionality
"""
import os
from typing import Any, Dict, List, Optional, Tuple

from app.ffmpeg.commands import FFmpegCommand
from app.ffmpeg.exceptions import FFmpegValidationError
from app.processors.base_processor import BaseProcessor
from app.utils.temp_files import create_temp_file, create_temp_dir


class VideoOverlay(BaseProcessor):
    """Video overlay processor for Picture-in-Picture (PiP) functionality"""

    def __init__(
        self,
        task_id: int,
        config: Dict[str, Any],
        progress_callback: Optional[Any] = None,
    ):
        super().__init__(task_id, config, progress_callback)
        self.base_file_id = config.get("base_video_file_id")
        self.overlay_file_id = config.get("overlay_video_file_id")
        self.base_file_path: Optional[str] = None
        self.overlay_file_path: Optional[str] = None

    async def validate_input(self) -> None:
        """
        Validate input: check file existence, resolutions, durations.
        Files should be provided via config['base_file_path'] and config['overlay_file_path']
        """
        base_path = self.config.get("base_file_path")
        overlay_path = self.config.get("overlay_file_path")
        
        if not base_path:
            raise FFmpegValidationError("base_file_path is required")
        if not overlay_path:
            raise FFmpegValidationError("overlay_file_path is required")
        
        if not os.path.isfile(base_path):
            raise FFmpegValidationError(f"Base video file not found: {base_path}")
        if not os.path.isfile(overlay_path):
            raise FFmpegValidationError(f"Overlay video file not found: {overlay_path}")
        
        self.base_file_path = base_path
        self.overlay_file_path = overlay_path
        
        # Get video info for both files
        base_info = await FFmpegCommand.get_video_info(base_path)
        overlay_info = await FFmpegCommand.get_video_info(overlay_path)
        
        # Validate that both are valid videos
        if not base_info.get("width") or not base_info.get("height"):
            raise FFmpegValidationError("Base video has invalid dimensions")
        if not overlay_info.get("width") or not overlay_info.get("height"):
            raise FFmpegValidationError("Overlay video has invalid dimensions")
        
        # Store info for processing
        self.config["base_info"] = base_info
        self.config["overlay_info"] = overlay_info
        
        # Check durations (overlay can be shorter or longer, we'll handle both)
        base_duration = base_info.get("duration", 0)
        overlay_duration = overlay_info.get("duration", 0)
        
        if base_duration == 0:
            raise FFmpegValidationError("Base video has zero duration")
        if overlay_duration == 0:
            raise FFmpegValidationError("Overlay video has zero duration")

    def _calculate_overlay_size(
        self, overlay_width: int, overlay_height: int
    ) -> Tuple[int, int]:
        """
        Calculate overlay size based on config.
        
        Uses width/height if specified, otherwise uses scale.
        
        Args:
            overlay_width: Original overlay video width
            overlay_height: Original overlay video height
            
        Returns:
            Tuple of (width, height) for the scaled overlay
        """
        config_data = self.config.get("config", {})
        
        # If explicit width/height are provided, use them
        if config_data.get("width") and config_data.get("height"):
            return config_data["width"], config_data["height"]
        
        # Otherwise use scale
        scale = config_data.get("scale", 0.2)
        scaled_width = int(overlay_width * scale)
        scaled_height = int(overlay_height * scale)
        
        return scaled_width, scaled_height

    def _color_to_hex(self, color: str) -> str:
        """
        Convert color from #RRGGBB format to FFmpeg hex format (0xRRGGBB).
        
        Args:
            color: Color in #RRGGBB format
            
        Returns:
            Color in 0xRRGGBB format for FFmpeg
        """
        if color.startswith("#"):
            return "0x" + color[1:]
        return color

    def _apply_shape_filter(self, width: int, height: int) -> str:
        """
        Apply shape filter to overlay video.
        
        Args:
            width: Overlay width
            height: Overlay height
            
        Returns:
            FFmpeg filter string for shape application
        """
        config_data = self.config.get("config", {})
        shape = config_data.get("shape", "rectangle")
        
        if shape == "rectangle":
            return ""
        
        if shape == "circle":
            # Use geq filter to create circular mask
            # Formula: pixels within radius of center are fully opaque, others transparent
            radius = min(width, height) // 2
            cx, cy = width // 2, height // 2
            filter_str = (
                f"format=alpha,"
                f"geq=lum='p(X,Y)':"
                f"a='st(1,a)*st(1,b)*hypot(X-{cx},Y-{cy})<={radius}?a:0'"
            )
            return filter_str
        
        if shape == "rounded":
            # Use geq filter to create rounded corners
            radius = config_data.get("border_radius", 10)
            # Limit radius to half of min dimension
            radius = min(radius, min(width, height) // 2)
            
            # Formula for rounded corners using distance from corners
            filter_str = (
                f"format=alpha,"
                f"geq=lum='p(X,Y)':"
                f"a='st(1,a)*st(1,b)*"
                f"hypot(min(X,W-X),min(Y,H-Y))>={radius}?"
                f"(hypot(min(X,W-X),min(Y,H-Y))-{radius})*a:{radius}*a'"
            )
            return filter_str
        
        return ""

    def _apply_border_filter(self, width: int, height: int) -> str:
        """
        Apply border filter to overlay video using drawbox.
        
        Args:
            width: Overlay width
            height: Overlay height
            
        Returns:
            FFmpeg filter string for border application
        """
        border_config = self.config.get("border", {})
        
        if not border_config.get("enabled", False):
            return ""
        
        border_width = border_config.get("width", 2)
        color = self._color_to_hex(border_config.get("color", "black"))
        
        # Draw box overlay
        # format=drawbox=x:y:w:h:color:thickness
        filter_str = f"drawbox=x=0:y=0:w={width}:h={height}:color={color}:t={border_width}"
        return filter_str

    def _apply_shadow_filter(self, width: int, height: int) -> str:
        """
        Apply shadow filter to overlay video.
        
        Args:
            width: Overlay width
            height: Overlay height
            
        Returns:
            FFmpeg filter string for shadow application
        """
        shadow_config = self.config.get("shadow", {})
        
        if not shadow_config.get("enabled", False):
            return ""
        
        offset_x = shadow_config.get("offset_x", 2)
        offset_y = shadow_config.get("offset_y", 2)
        blur = shadow_config.get("blur", 2)
        color = self._color_to_hex(shadow_config.get("color", "black"))
        
        # FFmpeg shadow filter: shadow=offset_x:offset_y:blur:color
        filter_str = f"shadow={offset_x}:{offset_y}:{blur}:{color}"
        return filter_str

    def _generate_ffmpeg_command(
        self, base_file: str, overlay_file: str, output_file: str
    ) -> List[str]:
        """
        Generate FFmpeg command for video overlay.
        
        Args:
            base_file: Path to base video
            overlay_file: Path to overlay video
            output_file: Path to output video
            
        Returns:
            List of FFmpeg command arguments
        """
        from app.config import get_settings
        settings = get_settings()
        ffmpeg = getattr(settings, "FFMPEG_PATH", "ffmpeg")
        
        # Get configuration
        config_data = self.config.get("config", {})
        base_info = self.config.get("base_info", {})
        overlay_info = self.config.get("overlay_info", {})
        
        # Calculate overlay size
        overlay_width, overlay_height = self._calculate_overlay_size(
            overlay_info.get("width", 640),
            overlay_info.get("height", 480)
        )
        
        # Build filter chain
        filters = []
        
        # 1. Scale overlay to target size
        filters.append(f"[1:v]scale={overlay_width}:{overlay_height}[scaled]")
        
        # 2. Apply shape filter
        shape_filter = self._apply_shape_filter(overlay_width, overlay_height)
        if shape_filter:
            filters.append(f"[scaled]{shape_filter}[shaped]")
            current_input = "[shaped]"
        else:
            current_input = "[scaled]"
        
        # 3. Apply shadow (before border)
        shadow_filter = self._apply_shadow_filter(overlay_width, overlay_height)
        if shadow_filter:
            filters.append(f"{current_input}{shadow_filter}[shadowed]")
            current_input = "[shadowed]"
        
        # 4. Apply border
        border_filter = self._apply_border_filter(overlay_width, overlay_height)
        if border_filter:
            filters.append(f"{current_input}{border_filter}[bordered]")
            current_input = "[bordered]"
        
        # 5. Apply opacity if needed
        opacity = config_data.get("opacity", 1.0)
        if opacity < 1.0:
            # Use colorchannelmixer to adjust alpha
            alpha_value = opacity
            filters.append(f"{current_input}format=alpha,colorchannelmixer=aa={alpha_value}[final_overlay]")
            current_input = "[final_overlay]"
        else:
            # Keep the current label
            if not current_input.startswith("["):
                # Add label if not present
                current_input = f"{current_input}[final_overlay]"
            else:
                current_input = f"{current_input}[final_overlay]"
        
        # 6. Overlay on base video
        x_pos = config_data.get("x", 10)
        y_pos = config_data.get("y", 10)
        
        # Build final filter chain
        if len(filters) > 0:
            filter_complex = ";".join(filters)
            filter_complex += f";[0:v]{current_input}overlay={x_pos}:{y_pos}"
        else:
            # Simple overlay without any filters
            filter_complex = f"[1:v]scale={overlay_width}:{overlay_height}[overlay];"
            filter_complex += f"[0:v][overlay]overlay={x_pos}:{y_pos}"
        
        # Build command
        cmd = [
            ffmpeg,
            "-y",  # Overwrite output
            "-i", base_file,  # Base video (input 0)
            "-i", overlay_file,  # Overlay video (input 1)
            "-filter_complex", filter_complex,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",  # Use shortest duration
            output_file,
        ]
        
        return cmd

    async def process(self) -> Dict[str, Any]:
        """
        Process video overlay: scale, apply effects, overlay on base, save.
        
        Returns:
            Dictionary with output_path
        """
        if not self.base_file_path or not self.overlay_file_path:
            raise FFmpegValidationError("File paths not set during validation")
        
        # Create output path
        output_path = self.config.get("output_path")
        if not output_path:
            output_path = create_temp_file(suffix=".mp4", prefix="overlay_")
            self.add_temp_file(output_path)
        
        # Generate and execute FFmpeg command
        cmd = self._generate_ffmpeg_command(
            self.base_file_path,
            self.overlay_file_path,
            output_path
        )
        
        # Get total duration for progress tracking
        base_info = self.config.get("base_info", {})
        total_duration = base_info.get("duration", 0)
        
        def progress_cb(progress: float) -> None:
            if total_duration and total_duration > 0 and progress is not None:
                pct = min(100.0, max(0.0, 100.0 * progress / total_duration))
                self.update_progress(pct)
            elif progress is not None:
                self.update_progress(progress)
        
        # Execute command
        timeout = self.config.get("timeout", 3600)
        await FFmpegCommand.run_command(
            cmd,
            timeout=timeout,
            progress_callback=progress_cb
        )
        
        self.update_progress(100.0)
        
        return {
            "output_path": output_path,
            "base_file_id": self.base_file_id,
            "overlay_file_id": self.overlay_file_id
        }
