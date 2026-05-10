# 02. Ядро FFmpeg: запуск, метаданные, прогресс, оптимизация

Все процессоры построены поверх единого слоя в `app/ffmpeg/`:

```
app/ffmpeg/
├── commands.py    # FFmpegCommand, FFmpegOptimizer, HardwareAccelerator
├── exceptions.py  # FFmpegError и потомки
└── utils.py       # parse_duration, format_duration, parse_ffmpeg_output, get_file_metadata
```

## 2.1 Исключения

`app/ffmpeg/exceptions.py`:

```python
class FFmpegError(Exception):                  # базовый
    pass

class FFmpegValidationError(FFmpegError):       # ошибка входных данных
    pass

class FFmpegProcessingError(FFmpegError):       # ненулевой код возврата FFmpeg
    pass

class FFmpegTimeoutError(FFmpegError):          # таймаут run_command
    pass
```

Иерархия очень плоская — этого достаточно. В Celery‑задачах
`FFmpegValidationError` маппится в `PermanentError` (не повторять),
`FFmpegTimeoutError` — частный случай (не повторяется по умолчанию, но
можно превратить в `TemporaryError` при необходимости).

## 2.2 `FFmpegCommand.run_command(...)`

Главная точка входа в FFmpeg/ffprobe.

```python
@staticmethod
async def run_command(
    command: list[str],
    timeout: int = 3600,
    progress_callback: Callable[[float], None] | None = None,
) -> str:
    """
    Запуск FFmpeg/ffprobe через asyncio subprocess.
    - Стримит stdout и stderr (8 KB чанками).
    - Если есть progress_callback — на каждый чанк stderr вызывает
      parse_ffmpeg_progress(chunk) и пробрасывает 0–100% (или текущее время
      в секундах, если total_duration не задан).
    - При asyncio.TimeoutError — proc.kill(), потом raise FFmpegTimeoutError.
    - При proc.returncode != 0 — raise FFmpegProcessingError(..., stderr[-2000:]).

    Returns: stdout как строка (utf-8, replace).
    """
```

Ключевые свойства, которые **обязательно повторить** при портировании:

1. **Async‑процесс с раздельным чтением stdout и stderr**, иначе при долгом
   рендере буфер заполнится и FFmpeg повиснет на write.
2. **Чанковое чтение** (8192 байт) — даёт «живой» прогресс без задержки.
3. **На таймауте — `kill()` и `await proc.wait()`** (а не `terminate()`,
   который FFmpeg может игнорировать).
4. **При ошибке возвращать последние ~2000 символов stderr** — достаточно для
   диагностики, не раздувает БД.

### Минимальный аналог на чистом Python (без зависимостей)

```python
import asyncio, re

TIME_RE = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})")

async def run_ffmpeg(cmd, timeout=3600, on_progress=None, total=None):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_chunks, stderr_chunks = [], []

    async def pump(stream, sink, parse=False):
        while True:
            chunk = await stream.read(8192)
            if not chunk:
                break
            sink.append(chunk)
            if parse and on_progress:
                m = TIME_RE.search(chunk.decode("utf-8", "replace"))
                if m:
                    h, mn, s = m.group(1).split(":")
                    cur = int(h)*3600 + int(mn)*60 + float(s)
                    on_progress(min(100, 100*cur/total) if total else cur)

    try:
        await asyncio.wait_for(asyncio.gather(
            pump(proc.stdout, stdout_chunks),
            pump(proc.stderr, stderr_chunks, parse=True),
            proc.wait(),
        ), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill(); await proc.wait()
        raise TimeoutError(f"FFmpeg timed out after {timeout}s")

    err = b"".join(stderr_chunks).decode("utf-8", "replace")
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg exit {proc.returncode}: {err[-2000:]}")
    return b"".join(stdout_chunks).decode("utf-8", "replace")
```

## 2.3 `FFmpegCommand.parse_ffmpeg_progress(stderr, total_duration=None)`

```python
m = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", stderr)
if not m:
    return None
current = parse_duration(m.group(1))   # → секунды (float)
if total_duration and total_duration > 0:
    return min(100.0, max(0.0, 100.0 * current / total_duration))
return current
```

FFmpeg в обычном режиме пишет `frame= 100 fps= 30 q=28.0 size= 256kB time=00:00:03.34 ...`
в stderr с регулярной частотой. Регулярка ловит только `time=...`.

> **Важно.** Если хочется точный прогресс — лучше передавать FFmpeg ключ
> `-progress pipe:1` (тогда он печатает структурированные `out_time_us=...`
> в stdout). В этом проекте используется простой парсинг stderr — сделано
> ради совместимости с любым flavor FFmpeg и отсутствия лишних аргументов.

## 2.4 `FFmpegCommand.get_video_info(file_path)`

Запускает ffprobe и парсит JSON. Возвращает компактный словарь:

```python
{
    "duration": 12.345,        # секунды
    "width": 1920,
    "height": 1080,
    "video_codec": "h264",     # codec_name первого видеопотока
    "fps": 29.97,              # из r_frame_rate "num/den"
}
```

Точная команда:

```
ffprobe -v quiet -print_format json -show_format -show_streams <file_path>
```

Реализация:

```python
out = await run_command([
    FFPROBE_PATH, "-v", "quiet",
    "-print_format", "json",
    "-show_format", "-show_streams",
    file_path,
], timeout=30)
data = json.loads(out)
# Из streams ищется первый с codec_type == "video".
# duration берется из format.duration.
# fps вычисляется как num/den из r_frame_rate.
```

Если в файле нет видеопотока — `width/height/video_codec/fps` будут `None`.

## 2.5 `FFmpegCommand.get_audio_info(file_path)`

То же `ffprobe -show_format -show_streams`, но возвращает:

```python
{
    "duration": 12.345,
    "audio_codec": "aac",      # codec_name первого audio stream
    "bitrate": 128000,         # из format.bit_rate (None если нет)
}
```

## 2.6 `FFmpegCommand.validate_file(file_path) -> bool`

Дешевая проверка «файл вообще читается?». Пытается `get_video_info`, при
исключении — `get_audio_info`. Возвращает `True` если хоть что‑то распарсилось.

## 2.7 `FFmpegOptimizer` — пресеты, tune, CRF, threads

```python
class FFmpegPreset(str, Enum):
    ULTRAFAST = "ultrafast"
    SUPERFAST = "superfast"
    VERYFAST  = "veryfast"
    FASTER    = "faster"
    FAST      = "fast"
    MEDIUM    = "medium"
    SLOW      = "slow"
    SLOWER    = "slower"
    VERYSLOW  = "veryslow"

class FFmpegTune(str, Enum):
    FILM        = "film"
    ANIMATION   = "animation"
    GRAIN       = "grain"
    STILLIMAGE  = "stillimage"
    FASTDECODE  = "fastdecode"
    ZEROLATENCY = "zerolatency"
```

Использование:

```python
opt = FFmpegOptimizer(preset=FFmpegPreset.FAST, tune=FFmpegTune.FILM,
                      crf=23, threads=4)
args = opt.get_encoding_params()
# → ['-preset', 'fast', '-tune', 'film', '-crf', '23', '-threads', '4']
```

Готовые сценарии:

```python
opt.optimize_for_scenario("fast")     # preset=veryfast, tune=fastdecode, threads=4
opt.optimize_for_scenario("balanced") # preset=fast,     tune=film,       threads=4
opt.optimize_for_scenario("quality")  # preset=medium,   tune=film, crf=18, threads=4
```

> В `VideoJoiner` оптимайзер вызывается, но к concat‑demuxer (`-c copy`) его
> параметры не применяются — это место зарезервировано на случай переключения
> на режим перекодирования (см. 03).

## 2.8 `HardwareAccelerator` — детект и параметры

```python
HardwareAccelerator.detect_available() -> list[str]
# Может вернуть подмножество ["nvenc", "qsv", "vaapi"]
```

Алгоритм детектирования (короткий timeout 5 c, ловит `FileNotFoundError`):

| Acc      | Чем проверяется                              |
| -------- | -------------------------------------------- |
| `nvenc`  | `nvidia-smi --query-gpu=name --format=csv`   |
| `vaapi`  | `vainfo`                                      |
| `qsv`    | `ffmpeg -hide_banner -hwaccels`, ищется `qsv`|

Аргументы для FFmpeg:

```python
HardwareAccelerator.get_hwaccel_params("nvenc")
# → ['-hwaccel', 'cuda', '-c:v', 'h264_nvenc']

HardwareAccelerator.get_hwaccel_params("qsv")
# → ['-hwaccel', 'qsv', '-c:v', 'h264_qsv']

HardwareAccelerator.get_hwaccel_params("vaapi")
# → ['-hwaccel', 'vaapi',
#    '-vaapi_device', '/dev/dri/renderD128',
#    '-c:v', 'h264_vaapi']
```

> В текущих процессорах HW‑acceleration **не подключен автоматически** —
> функция доступна, но решение об использовании остается за вызывающим кодом.
> При портировании имеет смысл выбирать энкодер один раз при старте сервиса
> и использовать его последовательно — иначе кеш FFmpeg/драйвера будет
> «прогреваться» каждый раз.

## 2.9 Утилиты времени и метаданных

`app/ffmpeg/utils.py`:

```python
def format_duration(seconds: float) -> str:
    # 65.123 → "00:01:05.123"

def parse_duration(s: str) -> float:
    # "00:01:05.123" → 65.123
    # "65.123"        → 65.123
    # "01:05.123"     → 65.123  (MM:SS.xx)
    # ""              → 0.0

def parse_ffmpeg_output(stderr: str) -> dict:
    # Извлекает: duration, video_codec, width, height, fps
    # Из строк FFmpeg вида "Duration: 00:01:23.45" и
    # "Video: h264 (High), yuv420p, 1920x1080, 30 fps".

def get_file_metadata(file_path: str) -> dict:
    # Без вызова FFmpeg, только os.stat:
    # {"exists": True/False, "size": int, "mtime": float}
```

## 2.10 Конфигурация

```python
# app/config.py
FFMPEG_PATH:    str = "/usr/bin/ffmpeg"
FFPROBE_PATH:   str = "/usr/bin/ffprobe"
FFMPEG_THREADS: int = 4
FFMPEG_PRESET:  str = "fast"
TASK_TIMEOUT:   int = 3600   # секунд для одной FFmpeg‑команды
```

В коде значения берутся через `getattr(settings, "FFMPEG_PATH", "ffmpeg")` —
если переменная не задана, используется бинарь из `$PATH`.

## 2.11 Чек‑лист для повторения

- [ ] Раздельное чтение stdout/stderr через `asyncio.subprocess`.
- [ ] Парсинг прогресса по регулярке `time=HH:MM:SS.xx` или
      `-progress pipe:1`.
- [ ] Жесткий timeout с `kill()`, не `terminate()`.
- [ ] Ограничение длины stderr в исключении (~2 KB).
- [ ] `ffprobe -print_format json -show_format -show_streams` для метаданных.
- [ ] Иерархия исключений: validation / processing / timeout.
- [ ] Конфигурируемые пути к `ffmpeg`/`ffprobe`.
- [ ] (Опционально) детект HW‑accel один раз на старте сервиса.

Дальше — описание процессоров. Начните с [03-video-join.md](03-video-join.md).
