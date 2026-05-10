# 09. Утилиты и хелперы

> **Источник:** `app/utils/subtitle_parsers.py`, `app/utils/temp_files.py`,
> `app/ffmpeg/utils.py`.

Здесь собрано всё «инфраструктурное», на чем строятся процессоры:
парсеры субтитров, работа с временными файлами, время/длительность,
конвертация цвета.

## 9.1 Субтитр‑парсеры (`app/utils/subtitle_parsers.py`)

Все парсеры возвращают **унифицированный** список словарей:

```python
[
  {"start": float_seconds,
   "end":   float_seconds,
   "text":  str,
   # для ASS/SSA дополнительно:
   "layer": int, "style": str, "name": str,
   "margin_l": int, "margin_r": int, "margin_v": int, "effect": str},
  ...
]
```

### `parse_srt(content: str) -> list[dict]`

Разбивает по `\n\s*\n` (пустые строки между блоками).
Блок:
```
1
00:00:01,000 --> 00:00:04,000
Hello
World
```

- Первая строка — индекс (опционально, проверяется `isdigit()`).
- Вторая — таймкод `HH:MM:SS,mmm --> HH:MM:SS,mmm` (запятая перед мс).
- Остальное — текст, склеивается через `\n`.

При неверном таймкоде — `ValueError`.

### `parse_vtt(content: str) -> list[dict]`

```
WEBVTT

00:00:01.000 --> 00:00:04.000
Hello
```

- Заголовок `WEBVTT` пропускается.
- Блоки `NOTE`, `STYLE` пропускаются.
- Cue settings (`align:center`, `position:50%`) после таймкода —
  игнорируются (regex принимает их без капчи).
- Время — точкой перед мс.

### `parse_ass(content: str) -> list[dict]`

```
Dialogue: 0,0:00:01.00,0:00:04.00,Default,,0,0,0,,Hello, world
```

- Парсятся **только** строки, начинающиеся с `Dialogue:` (заголовки
  `[Script Info]`, `[V4+ Styles]`, `[Events]` пропускаются).
- Поля разделены **запятыми**. Текст может содержать запятые
  (`split(",", 9)` — максимум 10 частей).
- Время `H:MM:SS.cc` (часов 1‑2 цифры; **«сотые» секунды**, не
  миллисекунды).
- ASS‑теги внутри текста (`{\b1}...{\b0}`, `{\c&H00FFFFFF&}`, `{\fad(...)}`)
  **не разбираются** — оставляются как есть. FFmpeg/libass рендерит их
  при наложении.

### `parse_ssa(content: str) -> list[dict]`

```python
def parse_ssa(content): return parse_ass(content)
```

SSA — предшественник ASS, формат `Dialogue` идентичен (отличаются только
заголовки, которые мы и так не парсим).

### Внутренние конвертеры времени

```python
_parse_srt_time(time_str)   # "00:00:01,500" → 1.5
_parse_vtt_time(time_str)   # "00:00:01.500" → 1.5
_parse_ass_time(time_str)   # "0:00:01.50"   → 1.5  (сотые!)
```

## 9.2 Работа с временными файлами (`app/utils/temp_files.py`)

```python
def create_temp_file(suffix="", prefix="ffmpeg_", directory=None) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=directory)
    os.close(fd)
    return path
```
Создает файл и **сразу закрывает** дескриптор (нам нужен только путь —
писать в файл будет FFmpeg).

```python
def create_temp_dir(prefix="ffmpeg_", suffix="") -> str:
    return tempfile.mkdtemp(suffix=suffix, prefix=prefix)
```

```python
def cleanup_temp_files(temp_files: list[str]) -> None:
    """Удаляет файлы; ошибки OSError тихо игнорирует."""
```

```python
def cleanup_old_files(directory: str, max_age_hours: int = 24) -> int:
    """
    В `directory` ищет все, что начинается с 'ffmpeg_', и удаляет старше
    max_age_hours. Возвращает количество удалённых.
    Удаляет и файлы, и директории (через shutil.rmtree).
    """
```

> Префикс `ffmpeg_` — критически важная деталь. Эта функция используется
> в `app/queue/periodic_tasks.py` как «уборщик»; если переименуете
> префикс — измените и здесь.

## 9.3 Парсинг и форматирование длительности (`app/ffmpeg/utils.py`)

### `format_duration(seconds: float) -> str`

```python
65.123 → "00:01:05.123"
3661.0 → "01:01:01.000"
```

Используется в логах и при формировании контентного диапазона.

### `parse_duration(s: str) -> float`

```python
"00:01:05.123" → 65.123          # HH:MM:SS.xxx
"01:05.123"    → 65.123          # MM:SS.xxx
"65.123"       → 65.123          # просто число секунд
""             → 0.0             # пустая строка
"abc"          → 0.0             # некорректный ввод (молча 0)
```

Используется в `parse_ffmpeg_progress` (`time=` из stderr) и в парсерах
субтитров (косвенно, через свои функции).

### `parse_ffmpeg_output(stderr: str) -> dict`

Дешевый «грубый» парсер stderr ffmpeg (когда не хочется звать ffprobe):

```
Duration: 00:01:23.45, ...
Stream #0:0: Video: h264 (High), yuv420p, 1920x1080, 30 fps, 30 tbr, ...
```

Из этого вытаскивается:
```python
{
  "duration":    83.45,
  "video_codec": "h264",
  "width":       1920,
  "height":      1080,
  "fps":         30.0,
}
```

Регулярки (упрощенно):
- `Duration:\s*(\d{2}:\d{2}:\d{2}\.\d{2})`
- `Video:\s*\w+\s*\(?([^,\)]+)\)?[^,]*,\s*(\d+)x(\d+)`
- `(\d+(?:\.\d+)?)\s*fps`

> На production обычно ffprobe надежнее. Этот парсер используется как
> fallback и в тестах.

### `get_file_metadata(file_path: str) -> dict`

**Не вызывает FFmpeg**, только `os.stat`:
```python
{
  "exists": True,
  "size":   123456,           # bytes
  "mtime":  1700000000.0,     # unix timestamp
}
```

## 9.4 Конвертация цвета

Раскидана по процессорам; для удобства — собрано здесь.

### `#RRGGBB` → ASS‑формат `&HAABBGGRR&`
(используется в `text_overlay.py`)

```python
def color_to_ass(color: str, alpha: float = 1.0) -> str:
    h = color.lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    a = int(255 * alpha)
    return f"&H{a:02X}{b}{g}{r}&"      # порядок: A B G R
```

> **Важно про alpha:** в текущем коде alpha=1.0 даёт `A=FF` («полностью
> непрозрачный» в семантике drawtext multiplier), но в ASS/libass
> alpha=`00` = непрозрачно, `FF` = прозрачно. Если переиспользуете
> функцию для libass force_style — **инвертируйте**: `a = int(255*(1-alpha))`.

### `#RRGGBB` → FFmpeg hex `0xRRGGBB`
(используется в `video_overlay.py` для `drawbox`)

```python
def color_to_drawbox(color: str) -> str:
    return "0x" + color.lstrip("#")
```

`drawbox`/`drawtext` спокойно понимают `0xRRGGBB`, а также именованные
цвета (`white`, `black`, `red`).

## 9.5 Полезные сниппеты

### Безопасное удаление
```python
def safe_unlink(path: str) -> None:
    try:
        if os.path.exists(path) and os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass
```

### Контекст «временный файл, гарантированно удалится»
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def temp_path(suffix=".mp4"):
    fd, p = tempfile.mkstemp(suffix=suffix, prefix="ffmpeg_")
    os.close(fd)
    try:
        yield p
    finally:
        try: os.remove(p)
        except OSError: pass
```

### Конвертер любого формата субтитров → стандартный list[dict]
```python
def parse_any(content: str, fmt: str) -> list[dict]:
    fmt = fmt.upper()
    if fmt == "SRT": return parse_srt(content)
    if fmt == "VTT": return parse_vtt(content)
    if fmt in ("ASS", "SSA"): return parse_ass(content)
    raise ValueError(f"Unsupported subtitle format: {fmt}")
```

### list[dict] → SRT‑строка (нужен `_format_srt_time`)
```python
def to_srt(entries: list[dict]) -> str:
    out = []
    for i, e in enumerate(entries, 1):
        out.append(str(i))
        out.append(f"{_format_srt_time(e['start'])} --> {_format_srt_time(e['end'])}")
        out.append(e['text'])
        out.append("")
    return "\n".join(out)

def _format_srt_time(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    ms = int((t % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
```

## 9.6 Чек‑лист, что забрать в свой проект

- [ ] `parse_srt`, `parse_vtt`, `parse_ass`, `parse_ssa` — почти 1‑в‑1.
- [ ] `parse_duration`, `format_duration` — простые и удобные.
- [ ] `create_temp_file`, `create_temp_dir`, `cleanup_temp_files` —
      типовая обертка над `tempfile`.
- [ ] `cleanup_old_files(prefix='ffmpeg_', age=24h)` — фоновая очистка
      (вызывайте из планировщика).
- [ ] **Доработать** конвертацию `color_to_ass` под libass (инвертировать
      alpha) — см. 9.4.
- [ ] **Поправить порядок escape** в text_overlay (`\\` должен быть
      первым, см. 05).
