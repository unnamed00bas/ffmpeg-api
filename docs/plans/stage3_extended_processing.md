# Этап 3: Расширенная обработка (Недели 6-8)

## Обзор этапа

Этап реализует все расширенные функции обработки видео: аудио оверлей, текстовый оверлей (с полным набором стилей и анимаций), субтитры (поддержка нескольких форматов), picture-in-picture и комбинированные операции для создания сложных цепочек обработки.

---

## Подзадача 3.1: Наложение аудио

### Задачи реализации

**AudioOverlay processor в [app/processors/audio_overlay.py](app/processors/audio_overlay.py):**

```python
class AudioOverlay(BaseProcessor):
    async def validate_input(self) -> None:
        """Валидация аудио файлов"""
        # Проверка существования видео файла
        # Проверка существования аудио файла
        # Проверка формата аудио
        # Проверка длительности
    
    async def process_replace(self) -> Dict[str, Any]:
        """Замена аудио дорожки"""
        # FFmpeg команда: -c:v copy -c:a aac
    
    async def process_mix(self) -> Dict[str, Any]:
        """Микс аудио с оригиналом"""
        # FFmpeg amix фильтр
        # Регулировка громкости
    
    async def process(self) -> Dict[str, Any]:
        """Основная обработка"""
        mode = self.config.get("mode", "replace")
        if mode == "replace":
            return await self.process_replace()
        elif mode == "mix":
            return await self.process_mix()
        else:
            raise ValueError(f"Unknown mode: {mode}")
    
    def _generate_ffmpeg_command_replace(
        self,
        video_file: str,
        audio_file: str,
        output_file: str
    ) -> List[str]:
        """Генерация FFmpeg команды для replace"""
        return [
            "ffmpeg",
            "-i", video_file,
            "-i", audio_file,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_file
        ]
    
    def _generate_ffmpeg_command_mix(
        self,
        video_file: str,
        audio_file: str,
        output_file: str,
        original_volume: float = 1.0,
        overlay_volume: float = 1.0
    ) -> List[str]:
        """Генерация FFmpeg команды для mix"""
        return [
            "ffmpeg",
            "-i", video_file,
            "-i", audio_file,
            "-filter_complex",
            f"[0:a]volume={original_volume}[a0];"
            f"[1:a]volume={overlay_volume}[a1];"
            f"[a0][a1]amix=inputs=2:duration=shortest[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            output_file
        ]
```

**Pydantic schemas в [app/schemas/audio_overlay.py](app/schemas/audio_overlay.py):**

```python
class AudioOverlayMode(str, Enum):
    REPLACE = "replace"
    MIX = "mix"

class AudioOverlayRequest(BaseModel):
    video_file_id: int
    audio_file_id: int
    mode: AudioOverlayMode = AudioOverlayMode.REPLACE
    offset: float = Field(default=0.0, ge=0, description="Смещение в секундах")
    duration: Optional[float] = Field(None, ge=0, description="Длительность аудио")
    original_volume: float = Field(default=1.0, ge=0, le=2, description="Громкость оригинала")
    overlay_volume: float = Field(default=1.0, ge=0, le=2, description="Громкость оверлея")
    output_filename: Optional[str] = None
```

**Celery task:**

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
)
def audio_overlay_task(self, task_id: int, config: dict) -> dict:
    """Celery задача для наложения аудио"""
```

**Task endpoint:**

```python
# POST /api/v1/tasks/audio-overlay
- Body: AudioOverlayRequest
- Response: TaskResponse
```

### Тестирование подзадачи 3.1

**Unit тесты AudioOverlay:**

*Валидация:*
- validate_input() проходит для валидных видео и аудио
- validate_input() выбрасывает исключение для несуществующего видео
- validate_input() выбрасывает исключение для несуществующего аудио
- validate_input() проверяет аудио формат

*Replace режим:*
- process_replace() заменяет аудио дорожку
- process_replace() копирует видео без перекодирования
- process_replace() кодирует аудио в AAC

*Mix режим:*
- process_mix() миксирует аудио дорожки
- process_mix() использует amix фильтр
- process_mix() регулирует громкость

*Генерация команд:*
- _generate_ffmpeg_command_replace() генерирует корректную команду
- _generate_ffmpeg_command_replace() использует -c:v copy
- _generate_ffmpeg_command_mix() генерирует корректную команду
- _generate_ffmpeg_command_mix() использует amix фильтр
- _generate_ffmpeg_command_mix() применяет volume фильтры

**Unit тесты schemas:**
- AudioOverlayRequest валидируется корректно
- AudioOverlayRequest имеет значения по умолчанию
- AudioOverlayRequest проверяет границы (volume, offset, duration)

**Интеграционные тесты:**

*Replace режим:*
- Аудио дорожка заменяется полностью
- Оригинальное аудио удалено
- Видео не перекодировано
- Выходной файл корректен

*Mix режим:*
- Аудио смешивается корректно
- Оба аудио слышны
- Громкость регулируется корректно
- Длительность минимальная из двух

*Синхронизация:*
- Offset работает корректно
- Duration обрезает аудио
- Пустое duration использует полную длительность

**API endpoint тесты:**
- POST /tasks/audio-overlay создает задачу
- Replace режим работает
- Mix режим работает
- Offset и duration работают
- Volume регулировка работает

**Regression тесты:**
- Разные аудио форматы (mp3, aac, wav, flac)
- Разная длительность аудио
- Разный volume (0.0 - 2.0)
- Offset больше длительности видео

---

## Подзадача 3.2: Наложение текста

### Задачи реализации

**Pydantic schemas в [app/schemas/text_overlay.py](app/schemas/text_overlay.py):**

```python
class TextPositionType(str, Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"

class TextPosition(BaseModel):
    type: TextPositionType = TextPositionType.RELATIVE
    # Для absolute:
    x: Optional[int] = None
    y: Optional[int] = None
    # Для relative:
    position: Optional[str] = None  # "top-left", "top-center", "top-right", "center-left", "center", "center-right", "bottom-left", "bottom-center", "bottom-right"
    margin_x: Optional[int] = 10
    margin_y: Optional[int] = 10

class TextStyle(BaseModel):
    font_family: str = "Arial"
    font_size: int = Field(default=24, ge=8, le=200)
    font_weight: str = Field(default="normal", pattern="^(normal|bold|bolder|lighter|100|200|300|400|500|600|700|800|900)$")
    color: str = Field(default="white", pattern="^#[0-9A-Fa-f]{6}$")
    alpha: float = Field(default=1.0, ge=0, le=1)

class TextBackground(BaseModel):
    enabled: bool = False
    color: str = Field(default="black", pattern="^#[0-9A-Fa-f]{6}$")
    alpha: float = Field(default=0.5, ge=0, le=1)
    padding: int = Field(default=10, ge=0)
    border_radius: int = Field(default=5, ge=0)

class TextBorder(BaseModel):
    enabled: bool = False
    width: int = Field(default=2, ge=0)
    color: str = Field(default="black", pattern="^#[0-9A-Fa-f]{6}$")

class TextShadow(BaseModel):
    enabled: bool = False
    offset_x: int = Field(default=2, ge=-50, le=50)
    offset_y: int = Field(default=2, ge=-50, le=50)
    blur: int = Field(default=2, ge=0, le=20)
    color: str = Field(default="black", pattern="^#[0-9A-Fa-f]{6}$")

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
    duration: float = Field(default=1.0, ge=0)
    delay: float = Field(default=0.0, ge=0)

class TextOverlayRequest(BaseModel):
    video_file_id: int
    text: str = Field(..., min_length=1, max_length=1000)
    position: TextPosition = Field(default_factory=TextPosition)
    style: TextStyle = Field(default_factory=TextStyle)
    background: TextBackground = Field(default_factory=TextBackground)
    border: TextBorder = Field(default_factory=TextBorder)
    shadow: TextShadow = Field(default_factory=TextShadow)
    animation: TextAnimation = Field(default_factory=TextAnimation)
    rotation: int = Field(default=0, ge=-360, le=360)
    opacity: float = Field(default=1.0, ge=0, le=1)
    start_time: float = Field(default=0.0, ge=0)
    end_time: Optional[float] = Field(None, ge=0)
    output_filename: Optional[str] = None
```

**TextOverlay processor в [app/processors/text_overlay.py](app/processors/text_overlay.py):**

```python
class TextOverlay(BaseProcessor):
    async def validate_input(self) -> None:
        """Валидация входных данных"""
        # Проверка существования видео
        # Проверка текста (пустой, спецсимволы)
        # Проверка временных границ
    
    async def process(self) -> Dict[str, Any]:
        """Наложение текста"""
        # Генерация drawtext фильтра
        # Генерация FFmpeg команды
        # Запуск обработки
    
    def _calculate_position(self) -> Tuple[str, str]:
        """Вычисление координат текста"""
        if self.position.type == "absolute":
            return str(self.position.x), str(self.position.y)
        else:
            return self._get_relative_position()
    
    def _get_relative_position(self) -> Tuple[str, str]:
        """Получение относительной позиции"""
        positions = {
            "top-left": ("10", "10"),
            "top-center": ("(w-tw)/2", "10"),
            "top-right": ("(w-tw-10)", "10"),
            "center-left": ("10", "(h-th)/2"),
            "center": ("(w-tw)/2", "(h-th)/2"),
            "center-right": ("(w-tw-10)", "(h-th)/2"),
            "bottom-left": ("10", "(h-th-10)"),
            "bottom-center": ("(w-tw)/2", "(h-th-10)"),
            "bottom-right": ("(w-tw-10)", "(h-th-10)"),
        }
        pos = self.position.position
        x = positions.get(pos, "10")
        y = positions.get(pos, "10")
        if pos in positions:
            return positions[pos]
        return x, y
    
    def _generate_drawtext_filter(self) -> str:
        """Генерация drawtext фильтра"""
        # Базовые параметры (text, font, fontsize, color)
        # Позиционирование (x, y)
        # Стили (background, border, shadow)
        # Анимации
        # Rotation
        # Opacity
        return f"drawtext={self._build_drawtext_params()}"
    
    def _build_drawtext_params(self) -> str:
        """Сборка параметров drawtext"""
        params = []
        # Text
        params.append(f"text='{self._escape_text(self.config['text'])}'")
        # Font
        params.append(f"fontfile='{self._get_font_path(self.config['style']['font_family'])}'")
        params.append(f"fontsize={self.config['style']['font_size']}")
        # Color
        params.append(f"fontcolor={self._color_to_hex(self.config['style']['color'])}")
        params.append(f"alpha={self.config['style']['alpha']}")
        # Position
        x, y = self._calculate_position()
        params.append(f"x={x}")
        params.append(f"y={y}")
        # Background
        if self.config['background']['enabled']:
            params.append(self._build_background_params())
        # Border
        if self.config['border']['enabled']:
            params.append(self._build_border_params())
        # Shadow
        if self.config['shadow']['enabled']:
            params.append(self._build_shadow_params())
        # Animation
        params.extend(self._build_animation_params())
        # Rotation
        if self.config['rotation'] != 0:
            params.append(f"rotation={self.config['rotation']}")
        # Opacity
        if self.config['opacity'] != 1.0:
            params.append(f"alpha={self.config['opacity']}")
        # Timing
        params.append(f"enable='between(t,{self.config['start_time']},{self.config.get('end_time', 'INF')})'")
        return ":".join(params)
    
    def _escape_text(self, text: str) -> str:
        """Экранирование спецсимволов"""
        return text.replace("'", "'\\''")
    
    def _color_to_hex(self, color: str) -> str:
        """Конвертация цвета в HEX для FFmpeg"""
        # #RRGGBB -> &HRRGGBB& (FFmpeg format)
        return f"&H{color[1:]}&"
```

**Celery task:**

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
)
def text_overlay_task(self, task_id: int, config: dict) -> dict:
    """Celery задача для наложения текста"""
```

**Task endpoint:**

```python
# POST /api/v1/tasks/text-overlay
- Body: TextOverlayRequest
- Response: TaskResponse
```

### Тестирование подзадачи 3.2

**Unit тесты schemas:**
- TextOverlayRequest валидируется корректно
- TextPosition работает в absolute режиме
- TextPosition работает в relative режиме
- TextStyle валидирует границы (font_size, color, alpha)
- TextBackground валидирует параметры
- TextBorder валидирует параметры
- TextShadow валидирует параметры
- TextAnimation валидирует типы

**Unit тесты TextOverlay:**

*Валидация:*
- validate_input() проходит для валидных данных
- validate_input() выбрасывает исключение для пустого текста
- validate_input() выбрасывает исключение для несуществующего видео

*Позиционирование:*
- _calculate_position() возвращает корректные absolute координаты
- _calculate_position() возвращает корректные relative координаты
- _get_relative_position() поддерживает все 9 позиций

*Генерация фильтров:*
- _generate_drawtext_filter() генерирует корректный фильтр
- _build_drawtext_params() собирает все параметры
- _escape_text() экранирует спецсимволы
- _color_to_hex() конвертирует цвета

*Компоненты:*
- _build_background_params() генерирует background параметры
- _build_border_params() генерирует border параметры
- _build_shadow_params() генерирует shadow параметры
- _build_animation_params() генерирует animation параметры

**Интеграционные тесты:**

*Базовый текст:*
- Простой текст без стилей работает
- Текст отображается корректно
- Текст соответствует настройкам

*Стили:*
- Font family работает
- Font size работает
- Font weight работает
- Color работает
- Alpha работает

*Позиционирование:*
- Absolute позиционирование работает
- Relative позиционирование работает
- Все 9 позиций работают
- Margins работают

*Background:*
- Background цвет работает
- Background alpha работает
- Padding работает
- Border radius работает

*Border:*
- Border работает
- Border width работает
- Border color работает

*Shadow:*
- Shadow работает
- Shadow offset работает
- Shadow blur работает
- Shadow color работает

*Анимации:*
- Fade in работает
- Fade out работает
- Fade (in+out) работает
- Slide влево работает
- Slide вправо работает
- Slide вверх работает
- Slide вниз работает
- Zoom in работает
- Zoom out работает

*Advanced:*
- Rotation работает
- Opacity работает
- Start time работает
- End time работает
- Многострочный текст работает

**API endpoint тесты:**
- POST /tasks/text-overlay создает задачу
- Все стили работают корректно
- Все анимации работают корректно
- Комбинированные настройки работают

**Regression тесты:**
- Разные font families
- Максимальный font size (200)
- Минимальный font size (8)
- Экстремальные значения opacity (0.0, 1.0)
- Экстремальные значения rotation (-360, 360)
- Длинный текст (1000 символов)

---

## Подзадача 3.3: Субтитры

### Задачи реализации

**Pydantic schemas в [app/schemas/subtitle.py](app/schemas/subtitle.py):**

```python
class SubtitleFormat(str, Enum):
    SRT = "srt"
    VTT = "vtt"
    ASS = "ass"
    SSA = "ssa"

class SubtitleStyle(BaseModel):
    font_name: str = "Arial"
    font_size: int = Field(default=20, ge=10, le=72)
    primary_color: str = Field(default="&H00FFFFFF", pattern="^&H[0-9A-Fa-f]{8}$")
    secondary_color: str = Field(default="&H000000FF", pattern="^&H[0-9A-Fa-f]{8}$")
    outline_color: str = Field(default="&H00000000", pattern="^&H[0-9A-Fa-f]{8}$")
    back_color: str = Field(default="&H80000000", pattern="^&H[0-9A-Fa-f]{8}$")
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikeout: bool = False
    scale_x: float = Field(default=1.0, ge=0, le=10)
    scale_y: float = Field(default=1.0, ge=0, le=10)
    spacing: float = Field(default=0.0, ge=-10, le=10)
    angle: float = Field(default=0.0, ge=-360, le=360)
    border_style: int = Field(default=1, ge=0, le=4)
    outline: float = Field(default=2.0, ge=0)
    shadow: float = Field(default=2.0, ge=0)
    alignment: int = Field(default=2, ge=1, le=9)
    margin_l: int = Field(default=10, ge=0)
    margin_r: int = Field(default=10, ge=0)
    margin_v: int = Field(default=10, ge=0)
    encoding: int = Field(default=1, ge=0, le=255)

class SubtitlePosition(BaseModel):
    position: Optional[str] = None  # "top", "center", "bottom"
    margin_x: int = Field(default=10, ge=0)
    margin_y: int = Field(default=10, ge=0)

class SubtitleRequest(BaseModel):
    video_file_id: int
    subtitle_file_id: Optional[int] = None
    subtitle_text: Optional[List[Dict[str, Any]]] = None
    format: SubtitleFormat = SubtitleFormat.SRT
    style: SubtitleStyle = Field(default_factory=SubtitleStyle)
    position: SubtitlePosition = Field(default_factory=SubtitlePosition)
    output_filename: Optional[str] = None
```

**Subtitle парсеры в [app/utils/subtitle_parsers.py](app/utils/subtitle_parsers.py):**

```python
from typing import List, Dict, Any

def parse_srt(content: str) -> List[Dict[str, Any]]:
    """Парсинг SRT формата"""
    # 1
    # 00:00:01,000 --> 00:00:04,000
    # Hello World
    entries = []
    blocks = content.strip().split("\n\n")
    for block in blocks:
        lines = block.split("\n")
        if len(lines) >= 3:
            index = lines[0]
            time_range = lines[1]
            text = "\n".join(lines[2:])
            start, end = time_range.split(" --> ")
            start_time = _parse_srt_time(start)
            end_time = _parse_srt_time(end)
            entries.append({
                "index": int(index),
                "start": start_time,
                "end": end_time,
                "text": text
            })
    return entries

def _parse_srt_time(time_str: str) -> float:
    """Парсинг времени SRT: HH:MM:SS,mmm"""
    hours, minutes, seconds_ms = time_str.split(":")
    seconds, milliseconds = seconds_ms.split(",")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000

def parse_vtt(content: str) -> List[Dict[str, Any]]:
    """Парсинг WebVTT формата"""
    # WEBVTT
    # 
    # 00:00:01.000 --> 00:00:04.000
    # Hello World
    entries = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        if "-->" in lines[i]:
            time_range = lines[i]
            start, end = time_range.split(" --> ")
            start_time = _parse_vtt_time(start)
            end_time = _parse_vtt_time(end)
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip() != "":
                text_lines.append(lines[i])
                i += 1
            text = "\n".join(text_lines)
            entries.append({
                "start": start_time,
                "end": end_time,
                "text": text
            })
        i += 1
    return entries

def _parse_vtt_time(time_str: str) -> float:
    """Парсинг времени WebVTT: HH:MM:SS.mmm"""
    hours, minutes, seconds_ms = time_str.split(":")
    seconds, milliseconds = seconds_ms.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(milliseconds) / 1000

def parse_ass(content: str) -> List[Dict[str, Any]]:
    """Парсинг ASS формата"""
    # [Events]
    # Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
    # Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello World
    entries = []
    lines = content.split("\n")
    for line in lines:
        if line.startswith("Dialogue:"):
            # Парсинг строки Dialogue
            parts = line[9:].split(",", 9)
            if len(parts) >= 10:
                layer = int(parts[0])
                start_time = _parse_ass_time(parts[1])
                end_time = _parse_ass_time(parts[2])
                style = parts[3]
                name = parts[4]
                margin_l = int(parts[5])
                margin_r = int(parts[6])
                margin_v = int(parts[7])
                effect = parts[8]
                text = parts[9]
                entries.append({
                    "layer": layer,
                    "start": start_time,
                    "end": end_time,
                    "style": style,
                    "name": name,
                    "margin_l": margin_l,
                    "margin_r": margin_r,
                    "margin_v": margin_v,
                    "effect": effect,
                    "text": text
                })
    return entries

def _parse_ass_time(time_str: str) -> float:
    """Парсинг времени ASS: H:MM:SS.mm"""
    hours, minutes, seconds_cs = time_str.split(":")
    seconds, centiseconds = seconds_cs.split(".")
    return int(hours) * 3600 + int(minutes) * 60 + int(seconds) + int(centiseconds) / 100

def parse_ssa(content: str) -> List[Dict[str, Any]]:
    """Парсинг SSA формата"""
    # SSA похож на ASS
    return parse_ass(content)
```

**SubtitleProcessor в [app/processors/subtitle_processor.py](app/processors/subtitle_processor.py):**

```python
class SubtitleProcessor(BaseProcessor):
    async def validate_input(self) -> None:
        """Валидация субтитров"""
        # Проверка видео файла
        # Проверка субтитров файла (если есть)
        # Проверка текста субтитров (если есть)
        # Проверка формата
    
    async def process(self) -> Dict[str, Any]:
        """Наложение субтитров"""
        # Парсинг субтитров (если файл)
        # Генерация субтитров (если текст)
        # Генерация FFmpeg команды
        # Запуск обработки
    
    def _parse_subtitle_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Парсинг файла субтитров"""
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        format_type = self.config.get("format", "srt")
        if format_type == "srt":
            return parse_srt(content)
        elif format_type == "vtt":
            return parse_vtt(content)
        elif format_type == "ass":
            return parse_ass(content)
        elif format_type == "ssa":
            return parse_ssa(content)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
    
    def _generate_subtitle_from_text(self) -> str:
        """Генерация файла субтитров из текста"""
        # Генерация SRT формата из конфигурации
        pass
    
    def _generate_ass_style(self) -> str:
        """Генерация ASS стилей"""
        style = self.config.get("style", {})
        return f"""Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{style.get('font_name','Arial')},{style.get('font_size',20)},{style.get('primary_color','&H00FFFFFF')},{style.get('secondary_color','&H000000FF')},{style.get('outline_color','&H00000000')},{style.get('back_color','&H80000000')},{style.get('bold',False)},{style.get('italic',False)},{style.get('underline',False)},{style.get('strikeout',False)},{style.get('scale_x',1.0)},{style.get('scale_y',1.0)},{style.get('spacing',0.0)},{style.get('angle',0.0)},{style.get('border_style',1)},{style.get('outline',2.0)},{style.get('shadow',2.0)},{style.get('alignment',2)},{style.get('margin_l',10)},{style.get('margin_r',10)},{style.get('margin_v',10)},{style.get('encoding',1)}"""
    
    def _generate_ffmpeg_command(
        self,
        video_file: str,
        subtitle_file: str,
        output_file: str
    ) -> List[str]:
        """Генерация FFmpeg команды для субтитров"""
        # Для ASS/SSA: subtitles фильтр
        # Для SRT/VTT: subtitles фильтр с конвертацией
        pass
```

**Celery task:**

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
)
def subtitle_task(self, task_id: int, config: dict) -> dict:
    """Celery задача для субтитров"""
```

**Task endpoint:**

```python
# POST /api/v1/tasks/subtitles
- Body: SubtitleRequest
- Response: TaskResponse
```

### Тестирование подзадачи 3.3

**Unit тесты парсеров:**

*parse_srt:*
- parse_srt() парсит корректный SRT
- parse_srt() возвращает корректные start/end времена
- parse_srt() возвращает корректный текст
- parse_srt() выбрасывает исключение для некорректного формата

*parse_vtt:*
- parse_vtt() парсит корректный WebVTT
- parse_vtt() возвращает корректные start/end времена
- parse_vtt() игнорирует WEBVTT заголовок

*parse_ass:*
- parse_ass() парсит корректный ASS
- parse_ass() возвращает корректные параметры
- parse_ass() обрабатывает Dialogue строки

*parse_ssa:*
- parse_ssa() парсит корректный SSA
- parse_ssa() использует ASS логику

**Unit тесты SubtitleProcessor:**
- validate_input() проверяет видео файл
- validate_input() проверяет субтитры файл
- validate_input() проверяет текст субтитров
- _parse_subtitle_file() парсит SRT
- _parse_subtitle_file() парсит VTT
- _parse_subtitle_file() парсит ASS
- _parse_subtitle_file() парсит SSA
- _generate_subtitle_from_text() генерирует SRT
- _generate_ass_style() генерирует ASS стили

**Интеграционные тесты:**

*SRT формат:*
- SRT субтитры накладываются корректно
- Синхронизация времени работает
- Текст отображается корректно

*VTT формат:*
- WebVTT субтитры накладываются корректно
- Синхронизация времени работает

*ASS формат:*
- ASS субтитры накладываются корректно
- Стили применяются корректно
- Позиционирование работает

*SSA формат:*
- SSA субтитры накладываются корректно

*Генерация из текста:*
- Субтитры генерируются из текста
- Формат корректен
- Время корректно

*Стили:*
- Font настройки работают
- Цвета работают
- Border работает
- Shadow работает
- Alignment работает
- Margins работают

**API endpoint тесты:**
- POST /tasks/subtitles создает задачу
- SRT формат работает
- VTT формат работает
- ASS формат работает
- SSA формат работает
- Генерация из текста работает
- Стили применяются корректно

**Regression тесты:**
- Разные длины субтитров
- Многострочные субтитры
- Спецсимволы в тексте
- Unicode символы

---

## Подзадача 3.4: Picture-in-Picture (Video Overlay)

### Задачи реализации

**Pydantic schemas в [app/schemas/video_overlay.py](app/schemas/video_overlay.py):**

```python
class OverlayShapeType(str, Enum):
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ROUNDED = "rounded"

class OverlayConfig(BaseModel):
    x: int = Field(default=10, ge=0, description="X позиция в пикселях")
    y: int = Field(default=10, ge=0, description="Y позиция в пикселях")
    width: Optional[int] = Field(None, gt=0, description="Ширина в пикселях")
    height: Optional[int] = Field(None, gt=0, description="Высота в пикселях")
    scale: float = Field(default=0.2, gt=0, le=1, description="Масштаб")
    opacity: float = Field(default=1.0, ge=0, le=1, description="Прозрачность")
    shape: OverlayShapeType = OverlayShapeType.RECTANGLE
    border_radius: int = Field(default=0, ge=0, description="Радиус скругления для rounded")
    
class BorderStyle(BaseModel):
    enabled: bool = False
    width: int = Field(default=2, ge=0)
    color: str = Field(default="black", pattern="^#[0-9A-Fa-f]{6}$")

class ShadowStyle(BaseModel):
    enabled: bool = False
    offset_x: int = Field(default=2, ge=-50, le=50)
    offset_y: int = Field(default=2, ge=-50, le=50)
    blur: int = Field(default=2, ge=0, le=20)
    color: str = Field(default="black", pattern="^#[0-9A-Fa-f]{6}$")

class VideoOverlayRequest(BaseModel):
    base_video_file_id: int
    overlay_video_file_id: int
    config: OverlayConfig = Field(default_factory=OverlayConfig)
    border: BorderStyle = Field(default_factory=BorderStyle)
    shadow: ShadowStyle = Field(default_factory=ShadowStyle)
    output_filename: Optional[str] = None
```

**VideoOverlay processor в [app/processors/video_overlay.py](app/processors/video_overlay.py):**

```python
class VideoOverlay(BaseProcessor):
    async def validate_input(self) -> None:
        """Валидация overlay видео"""
        # Проверка существования base видео
        # Проверка существования overlay видео
        # Проверка разрешений
        # Проверка длительностей
    
    async def process(self) -> Dict[str, Any]:
        """Наложение видео"""
        # Масштабирование overlay видео
        # Применение эффектов (shape, border, shadow)
        # Наложение на base видео
        # Сохранение результата
    
    def _calculate_overlay_size(
        self,
        overlay_width: int,
        overlay_height: int
    ) -> Tuple[int, int]:
        """Вычисление размера overlay"""
        config = self.config.get("config", {})
        if "width" in config and "height" in config:
            return config["width"], config["height"]
        
        scale = config.get("scale", 0.2)
        return int(overlay_width * scale), int(overlay_height * scale)
    
    def _generate_ffmpeg_command(
        self,
        base_file: str,
        overlay_file: str,
        output_file: str
    ) -> List[str]:
        """Генерация FFmpeg команды"""
        # Масштабирование overlay
        # Применение формы (circle, rounded)
        # Применение border
        # Применение shadow
        # Наложение через overlay фильтр
        pass
    
    def _apply_shape_filter(self) -> str:
        """Применение формы к overlay"""
        shape = self.config.get("config", {}).get("shape", "rectangle")
        if shape == "circle":
            return "format=alpha,geq=lum='p(X,Y)':a='st(1,a)*st(1,b)*hypot(X-w/2,Y-h/2)<=min(w,h)/2?a:0'"
        elif shape == "rounded":
            radius = self.config.get("config", {}).get("border_radius", 10)
            return f"format=alpha,geq=lum='p(X,Y)':a='st(1,a)*st(1,b)*((hypot(X-w/2,Y-h/2)<=min(w,h)/2-st(3))?1:0)'"
        return ""
    
    def _apply_border_filter(self) -> str:
        """Применение border"""
        border = self.config.get("border", {})
        if border.get("enabled", False):
            width = border.get("width", 2)
            color = self._color_to_hex(border.get("color", "black"))
            return f"drawbox=w=iw-2*{width}:h=ih-2*{width}:t={width}:color={color}"
        return ""
    
    def _apply_shadow_filter(self) -> str:
        """Применение shadow"""
        shadow = self.config.get("shadow", {})
        if shadow.get("enabled", False):
            offset_x = shadow.get("offset_x", 2)
            offset_y = shadow.get("offset_y", 2)
            blur = shadow.get("blur", 2)
            color = self._color_to_hex(shadow.get("color", "black"))
            return f"shadow={offset_x}:{offset_y}:{blur}:{color}"
        return ""
```

**Celery task:**

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
)
def video_overlay_task(self, task_id: int, config: dict) -> dict:
    """Celery задача для picture-in-picture"""
```

**Task endpoint:**

```python
# POST /api/v1/tasks/video-overlay
- Body: VideoOverlayRequest
- Response: TaskResponse
```

### Тестирование подзадачи 3.4

**Unit тесты schemas:**
- VideoOverlayRequest валидируется корректно
- OverlayConfig валидирует границы (x, y, scale, opacity)
- BorderStyle валидирует параметры
- ShadowStyle валидирует параметры

**Unit тесты VideoOverlay:**

*Валидация:*
- validate_input() проходит для валидных видео
- validate_input() проверяет существование файлов

*Расчет размера:*
- _calculate_overlay_size() использует заданные width/height
- _calculate_overlay_size() использует scale если нет width/height
- _calculate_overlay_size() возвращает корректные значения

*Фильтры:*
- _apply_shape_filter() генерирует circle фильтр
- _apply_shape_filter() генерирует rounded фильтр
- _apply_border_filter() генерирует border фильтр
- _apply_shadow_filter() генерирует shadow фильтр

**Интеграционные тесты:**

*Базовый overlay:*
- Простой overlay работает
- Позиционирование работает (x, y)
- Масштабирование работает (scale)
- Размер работает (width, height)

*Формы:*
- Rectangle форма работает
- Circle форма работает
- Rounded форма работает
- Border radius работает

*Стили:*
- Opacity работает
- Border работает
- Shadow работает
- Сочетание стилей работает

*Несколько overlay:*
- Два overlay работают одновременно
- Три overlay работают одновременно

**API endpoint тесты:**
- POST /tasks/video-overlay создает задачу
- Все формы работают
- Все стили работают
- Несколько overlay работают

**Regression тесты:**
- Разные размеры overlay
- Разные позиции
- Экстремальные значения opacity (0.0, 1.0)
- Экстремальные значения scale (0.01, 1.0)

---

## Подзадача 3.5: Комбинированные операции

### Задачи реализации

**Pydantic schemas в [app/schemas/combined.py](app/schemas/combined.py):**

```python
class OperationType(str, Enum):
    JOIN = "join"
    AUDIO_OVERLAY = "audio_overlay"
    TEXT_OVERLAY = "text_overlay"
    SUBTITLES = "subtitles"
    VIDEO_OVERLAY = "video_overlay"

class Operation(BaseModel):
    type: OperationType
    config: Dict[str, Any]

class CombinedRequest(BaseModel):
    operations: List[Operation] = Field(..., min_length=2, max_length=10)
    base_file_id: int
    output_filename: Optional[str] = None
```

**CombinedProcessor в [app/processors/combined_processor.py](app/processors/combined_processor.py):**

```python
from typing import List, Dict, Any
import os

class CombinedProcessor(BaseProcessor):
    def __init__(
        self,
        task_id: int,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None
    ):
        super().__init__(task_id, config, progress_callback)
        self.intermediate_files: List[str] = []
    
    async def validate_input(self) -> None:
        """Валидация pipeline"""
        # Проверка количества операций (минимум 2, максимум 10)
        # Проверка совместимости операций
        # Проверка base файла
    
    async def process(self) -> Dict[str, Any]:
        """Выполнение pipeline"""
        operations = self.config.get("operations", [])
        base_file_id = self.config.get("base_file_id")
        
        # Загрузка base файла
        current_file = await self._load_file(base_file_id)
        self.add_temp_file(current_file)
        
        # Выполнение операций последовательно
        for i, operation in enumerate(operations):
            self.update_progress((i / len(operations)) * 100)
            
            try:
                result_file = await self._execute_operation(
                    operation,
                    current_file
                )
                
                # Удаление предыдущего файла
                if current_file in self.temp_files:
                    self.temp_files.remove(current_file)
                os.remove(current_file)
                
                current_file = result_file
                self.add_temp_file(current_file)
                
            except Exception as e:
                # Откат при ошибке
                await self._rollback()
                raise
        
        # Финальный файл
        self.update_progress(100)
        
        # Загрузка результата в MinIO
        result_file_id = await self._upload_result(current_file)
        
        return {
            "result_file_id": result_file_id,
            "operations_count": len(operations)
        }
    
    async def _execute_operation(
        self,
        operation: Dict[str, Any],
        input_file: str
    ) -> str:
        """Выполнение одной операции"""
        op_type = operation.get("type")
        op_config = operation.get("config", {})
        
        # Создание процессора для операции
        if op_type == "audio_overlay":
            processor = AudioOverlay(
                self.task_id,
                op_config,
                None  # No progress callback for individual ops
            )
        elif op_type == "text_overlay":
            processor = TextOverlay(
                self.task_id,
                op_config,
                None
            )
        elif op_type == "subtitles":
            processor = SubtitleProcessor(
                self.task_id,
                op_config,
                None
            )
        elif op_type == "video_overlay":
            processor = VideoOverlay(
                self.task_id,
                op_config,
                None
            )
        else:
            raise ValueError(f"Unsupported operation type: {op_type}")
        
        # Валидация
        await processor.validate_input()
        
        # Подготовка конфигурации с input file
        processor.config["input_file"] = input_file
        
        # Выполнение
        result = await processor.process()
        
        return result.get("output_file")
    
    async def _rollback(self) -> None:
        """Откат при ошибке"""
        # Очистка всех временных файлов
        await self.cleanup()
    
    async def cleanup(self) -> None:
        """Очистка всех временных файлов"""
        # Удаление temp files
        await super().cleanup()
        
        # Удаление intermediate files
        for intermediate_file in self.intermediate_files:
            if os.path.exists(intermediate_file):
                os.remove(intermediate_file)
        self.intermediate_files.clear()
```

**Celery task:**

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
)
def combined_task(self, task_id: int, config: dict) -> dict:
    """Celery задача для комбинированных операций"""
```

**Task endpoint:**

```python
# POST /api/v1/tasks/combined
- Body: CombinedRequest
- Response: TaskResponse
```

### Тестирование подзадачи 3.5

**Unit тесты schemas:**
- CombinedRequest валидируется корректно
- CombinedRequest проверяет количество операций (2-10)
- Operation валидирует тип и config

**Unit тесты CombinedProcessor:**

*Валидация:*
- validate_input() проходит для 2+ операций
- validate_input() выбрасывает исключение для 1 операции
- validate_input() выбрасывает исключение для 11+ операций

*Выполнение pipeline:*
- process() выполняет операции последовательно
- process() обновляет прогресс корректно
- process() передает output одной операции в input следующей

*Обработка ошибок:*
- Ошибка в операции вызывает rollback
- Ошибка в операции удаляет все temp файлы
- Ошибка в операции удаляет intermediate files

*Cleanup:*
- cleanup() удаляет temp файлы
- cleanup() удаляет intermediate файлы
- cleanup() очищает все списки

**Интеграционные тесты:**

*Простой pipeline:*
- 2 операции работают корректно
- 3 операции работают корректно

*Сложный pipeline:*
- 5 операций работают корректно
- 10 операций работают корректно

*Разные типы операций:*
- Audio + Text overlay
- Text + Video overlay
- Audio + Text + Subtitles
- Сложный pipeline со всеми типами

*Откат:*
- Ошибка в середине pipeline вызывает rollback
- Все временные файлы удалены при ошибке

**API endpoint тесты:**
- POST /tasks/combined создает задачу
- Простые pipeline работают
- Сложные pipeline работают
- Откат работает при ошибке

**Regression тесты:**
- Разные порядки операций
- Одинаковые типы операций подряд
- Максимальное количество операций (10)

---

## Критерии завершения Этапа 3

**Функциональные требования:**
- Наложение аудио работает (replace и mix режимы)
- Наложение текста работает (все стили, анимации)
- Субтитры работают (SRT, VTT, ASS, SSA форматы)
- Picture-in-picture работает (все формы и стили)
- Комбинированные операции работают (pipeline)
- Все процессоры используют BaseProcessor
- Все Celery задачи работают

**Требования к тестированию:**
- Все unit тесты проходят
- Все интеграционные тесты проходят
- Coverage > 80% для кода этапа 3

**Документация:**
- Все процессоры документированы (docstrings)
- Все schemas документированы
- API endpoints документированы в OpenAPI
- Примеры использования добавлены

**Производительность:**
- Аудио overlay < 1.5x реального времени
- Текстовый overlay < 1.2x реального времени
- Субтитры < 1.2x реального времени
- Video overlay < 1.5x реального времени
- Pipeline масштабируется линейно
