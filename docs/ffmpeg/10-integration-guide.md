# 10. Гайд по реализации в другом проекте

Этот документ — практический чек‑лист и эталонные примеры для портирования
FFmpeg‑функционала в другой проект (необязательно Python/FastAPI).

## 10.1 С чего начать

1. **Установите FFmpeg ≥ 4.4** с поддержкой `libx264`, `libfreetype` (для
   `drawtext`) и `libass` (для `subtitles`):

   ```bash
   # Debian/Ubuntu
   apt-get install -y ffmpeg fonts-liberation fonts-dejavu

   # macOS (Homebrew)
   brew install ffmpeg

   # Alpine (Docker)
   apk add --no-cache ffmpeg ttf-dejavu
   ```

   Проверьте:
   ```bash
   ffmpeg -version | head -1
   ffmpeg -hide_banner -filters | grep -E "(drawtext|subtitles|overlay|amix|drawbox)"
   # должно отдать все пять
   ```

2. **Решите, нужна ли асинхронность.** Все процессоры в проекте — `async`
   (поверх `asyncio.create_subprocess_exec`). Если это лишнее — обертка
   через обычный `subprocess.Popen` с `Popen.stderr.readline()` цикле
   будет проще.

3. **Решите, как сериализовать прогресс**: writeback в БД, push в Redis
   pub/sub, WebSocket клиенту, или просто в файл‑лог. В оригинале — write
   в Postgres‑строку `tasks.progress` на каждом callback.

4. **Файлы вход/выход.** Процессоры работают **только с локальными
   путями**. Скачивание из S3/MinIO/HTTP — задача оркестратора (как в
   `app/queue/tasks.py`).

## 10.2 Минимальная переносимая структура

```
your_project/
├── ffmpeg_core/
│   ├── runner.py          # run_ffmpeg(), parse_progress
│   ├── probe.py           # get_video_info, get_audio_info
│   └── exceptions.py      # FFmpegError, FFmpegValidationError, FFmpegTimeoutError
├── ops/
│   ├── join.py            # build_join_cmd(...)
│   ├── audio_overlay.py   # build_audio_replace_cmd / build_audio_mix_cmd
│   ├── text_overlay.py    # build_text_overlay_filter
│   ├── subtitles.py       # build_subtitles_filter
│   └── pip.py             # build_pip_filter_complex
├── utils/
│   ├── escape.py          # ASS color, drawtext escape
│   ├── temp_files.py      # create_temp_file, cleanup_old_files
│   └── subtitle_parsers.py
└── pipeline.py            # последовательное исполнение шагов
```

Никакого DI/ORM — функции возвращают `list[str]` (аргументы FFmpeg) или
строку фильтр‑графа. Так легче тестировать и интегрировать в любой стек.

## 10.3 Шаблон обертки `run_ffmpeg`

```python
import asyncio, re

TIME_RE = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})")

class FFmpegError(Exception): ...
class FFmpegTimeout(FFmpegError): ...

def parse_time(s: str) -> float:
    h, m, sec = s.split(":")
    return int(h)*3600 + int(m)*60 + float(sec)

async def run_ffmpeg(cmd: list[str], *, timeout: int = 3600,
                     total: float | None = None,
                     on_progress=None) -> str:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out_chunks, err_chunks = [], []

    async def read(stream, sink, parse=False):
        while True:
            chunk = await stream.read(8192)
            if not chunk:
                break
            sink.append(chunk)
            if parse and on_progress:
                m = TIME_RE.search(chunk.decode("utf-8", "replace"))
                if m:
                    cur = parse_time(m.group(1))
                    on_progress(min(100.0, 100.0*cur/total) if total else cur)

    try:
        await asyncio.wait_for(asyncio.gather(
            read(proc.stdout, out_chunks),
            read(proc.stderr, err_chunks, parse=True),
            proc.wait(),
        ), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill(); await proc.wait()
        raise FFmpegTimeout(f"FFmpeg timed out after {timeout}s")

    err = b"".join(err_chunks).decode("utf-8", "replace")
    if proc.returncode != 0:
        raise FFmpegError(f"exit {proc.returncode}: {err[-2000:]}")
    return b"".join(out_chunks).decode("utf-8", "replace")
```

## 10.4 Шаблон `probe.py`

```python
import asyncio, json
from .runner import run_ffmpeg

async def get_video_info(path, ffprobe="ffprobe"):
    out = await run_ffmpeg(
        [ffprobe, "-v", "quiet", "-print_format", "json",
         "-show_format", "-show_streams", path],
        timeout=30,
    )
    data = json.loads(out)
    info = {"duration": 0.0, "width": None, "height": None,
            "video_codec": None, "fps": None}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video":
            info["width"]  = int(s.get("width", 0))
            info["height"] = int(s.get("height", 0))
            info["video_codec"] = s.get("codec_name")
            num, den = s.get("r_frame_rate", "0/1").split("/")
            if int(den):
                info["fps"] = float(num)/int(den)
            break
    fmt = data.get("format", {})
    if "duration" in fmt:
        info["duration"] = float(fmt["duration"])
    return info
```

## 10.5 Эталонные команды по операциям

### JOIN (concat demuxer)
```bash
# 1) Список файлов
cat > list.txt <<'EOF'
file 'in1.mp4'
file 'in2.mp4'
EOF
# 2) Склейка без перекодирования
ffmpeg -y -f concat -safe 0 -i list.txt -c copy out.mp4
```
**Условие:** одинаковые кодек/разрешение/FPS.

### REPLACE AUDIO
```bash
ffmpeg -y -i video.mp4 -i audio.mp3 \
  -map 0:v:0 -map 1:a:0 \
  -c:v copy -c:a aac \
  -shortest out.mp4
```

### MIX AUDIO
```bash
ffmpeg -y -i video.mp4 -ss 0 -i audio.mp3 \
  -filter_complex "[1:a]volume=0.5[a1];[0:a]volume=1.0[a0];\
[a0][a1]amix=inputs=2:duration=first:dropout_transition=2" \
  -c:v copy -c:a aac \
  out.mp4
```

### TEXT OVERLAY (drawtext)
```bash
ffmpeg -y -i video.mp4 \
  -vf "drawtext=text='Hello':fontfile='DejaVuSans.ttf':\
fontsize=48:fontcolor=white:x=(w-tw)/2:y=h-th-30:\
enable='between(t,0,5)'" \
  -c:a copy out.mp4
```

### SUBTITLES (subtitles фильтр + force_style)
```bash
ffmpeg -y -i video.mp4 \
  -vf "subtitles='subs.srt':force_style='Fontname=DejaVu Sans,\
Fontsize=24,PrimaryColour=&H00FFFFFF,Outline=2,Alignment=2'" \
  -c:a copy out.mp4
```

### PIP (overlay)
```bash
ffmpeg -y -i base.mp4 -i overlay.mp4 \
  -filter_complex "[1:v]scale=480:270[ov];[0:v][ov]overlay=20:20" \
  -c:v libx264 -preset fast -crf 23 \
  -c:a aac -b:a 128k \
  -shortest out.mp4
```

### Прозрачность overlay (через colorchannelmixer)
```bash
ffmpeg -y -i base.mp4 -i overlay.mp4 \
  -filter_complex "[1:v]scale=480:270,format=yuva420p,\
colorchannelmixer=aa=0.7[ov];[0:v][ov]overlay=20:20" \
  -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k \
  -shortest out.mp4
```

## 10.6 Pipeline без оркестратора (CLI‑style)

```python
import asyncio, os, tempfile

async def pipeline(steps, base, out):
    """
    steps = [
      {"build_cmd": fn(input_path) -> (cmd, out_path)},
      ...
    ]
    """
    current = base
    intermediates = []
    try:
        for step in steps:
            cmd, next_path = step["build_cmd"](current)
            await run_ffmpeg(cmd)
            if current != base:
                os.remove(current)
            intermediates.append(next_path)
            current = next_path
        os.replace(current, out)
    except Exception:
        for p in intermediates:
            try: os.remove(p)
            except OSError: pass
        raise

# Пример шага: subtitles → text overlay → join с outro
def step_subs(srt_path):
    def build(input_path):
        out_path = tempfile.mkstemp(suffix=".mp4")[1]
        return ([
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"subtitles='{srt_path}'",
            "-c:a", "copy", out_path,
        ], out_path)
    return {"build_cmd": build}

asyncio.run(pipeline([step_subs("subs.srt")], "in.mp4", "out.mp4"))
```

## 10.7 Карта «фича оригинала → как реализовать у себя»

| Фича оригинала                              | Что нужно сделать у себя |
| ------------------------------------------- | ------------------------ |
| Pydantic‑валидация запроса                  | любой schema‑валидатор: zod, joi, pydantic, pojo + validators |
| FastAPI endpoint                            | любой HTTP‑фреймворк |
| Celery + Redis broker                       | RQ, ARQ, BullMQ, Sidekiq, голый thread‑pool |
| MinIO + boto3                               | любой S3‑совместимый client; для локала — просто файлы |
| PostgreSQL + SQLAlchemy для tasks/files     | любой движок и ORM; минимум — две таблицы |
| `BaseProcessor` (validate→process→cleanup)  | контракт класса, легко переписывается на любом языке |
| `FFmpegCommand.run_command`                 | см. 10.3 |
| `parse_ffmpeg_progress` по `time=...`       | regex `time=(\d{2}:\d{2}:\d{2}\.\d{2})` |
| Кеш метаданных ffprobe                      | LRU/Redis по `(file_id, mtime)` |
| HW‑accel detect (`nvenc`/`qsv`/`vaapi`)     | один раз при старте, выбрать энкодер |
| Cleanup старых temp файлов                  | cron / fs‑watcher / периодическая Celery‑задача |

## 10.8 Чек‑лист «не забыть»

- [ ] **Экранирование путей** в concat list (`'\''`).
- [ ] **Экранирование текста** в `drawtext` (`\\` должен быть **первым**, потом `:`, `=`, `#`, `[`, `]`, `{`, `}`, `%`, `'`).
- [ ] **`-shortest`** при наложении аудио или PiP — иначе странная длительность.
- [ ] **`-c:v copy`** там, где не нужно перекодирование (быстрее в десятки раз).
- [ ] **`-vaapi_device /dev/dri/renderD128`** при VAAPI.
- [ ] **Шрифты** — без них `drawtext`/`subtitles` падают или используют fallback.
- [ ] **libass** в FFmpeg — без него `subtitles` фильтра не существует.
- [ ] **Таймауты** на всех уровнях: FFmpeg `-timeout`, наш `asyncio.wait_for`, очередь tasks.
- [ ] **Очистка temp** — обязательно в `finally`, иначе диск переполнится.
- [ ] **Прогресс‑callback** — пускать дросселирование (например, не чаще 1×/сек).

## 10.9 Тестирование

В оригинале есть тесты в `tests/` (unit + integration). Минимальный набор
проверок при портировании:

1. **`get_video_info`** на: пустой файл, файл с двумя видеопотоками, файл
   с `r_frame_rate=0/0` (без видео).
2. **`parse_ffmpeg_progress`** на пустую строку, несколько `time=` в одной
   строке (должен брать **последний**).
3. **`parse_srt/vtt/ass`** на: блок без индекса, многострочный текст,
   запятые в `Dialogue:`, BOM в начале файла.
4. **Escape drawtext** на тексте `It's $5: 100% — [test] {ok}`.
5. **Концат** на 2 файла **разного** разрешения — должен бросить
   `FFmpegValidationError`.
6. **Audio mix** на видео без аудиодорожки — ожидаемое падение FFmpeg.
7. **PiP** с `opacity=0.5` — на финальном кадре должна быть видна
   полупрозрачная картинка.

## 10.10 Минимальный «всё в одном» пример (Python, без БД и MinIO)

```python
"""
mini_ffmpeg_service.py — независимый CLI для всех операций.
Запуск: python mini_ffmpeg_service.py <op> [args...]
"""
import asyncio, os, re, sys, tempfile, json

TIME_RE = re.compile(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})")

async def run(cmd, *, timeout=3600):
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    err = []
    async def pump(s, sink):
        while True:
            chunk = await s.read(8192)
            if not chunk: break
            sink.append(chunk)
    await asyncio.wait_for(asyncio.gather(
        pump(proc.stdout, []), pump(proc.stderr, err), proc.wait()),
        timeout=timeout)
    if proc.returncode != 0:
        raise SystemExit(b"".join(err).decode("utf-8", "replace")[-2000:])

def escape_drawtext(t):
    repls = [("\\","\\\\"),("'","'\\''"),(":","\\:"),("=","\\="),
             ("#","\\#"),("[","\\["),("]","\\]"),("{","\\{"),("}","\\}"),
             ("%","\\%")]
    for a,b in repls: t = t.replace(a,b)
    return t

async def op_join(files, out):
    fd, lst = tempfile.mkstemp(suffix=".txt"); os.close(fd)
    with open(lst,"w",encoding="utf-8") as f:
        for p in files:
            f.write(f"file '{p.replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
    try:
        await run(["ffmpeg","-y","-f","concat","-safe","0","-i",lst,
                   "-c","copy",out])
    finally:
        os.remove(lst)

async def op_replace_audio(video, audio, out):
    await run(["ffmpeg","-y","-i",video,"-i",audio,
               "-map","0:v:0","-map","1:a:0",
               "-c:v","copy","-c:a","aac","-shortest",out])

async def op_text(video, text, out, *, x="(w-tw)/2", y="h-th-30",
                  size=48, color="white", start=0, end=None):
    enable = f"between(t,{start},{end})" if end else f"gte(t,{start})"
    vf = (f"drawtext=text='{escape_drawtext(text)}':"
          f"fontsize={size}:fontcolor={color}:"
          f"x={x}:y={y}:enable='{enable}'")
    await run(["ffmpeg","-y","-i",video,"-vf",vf,"-c:a","copy",out])

async def op_subs(video, srt_path, out):
    vf = f"subtitles='{srt_path}'"
    await run(["ffmpeg","-y","-i",video,"-vf",vf,"-c:a","copy",out])

async def op_pip(base, overlay, out, *, x=10, y=10, scale=0.25):
    info = json.loads((await asyncio.create_subprocess_exec(
        "ffprobe","-v","quiet","-print_format","json",
        "-show_streams","-select_streams","v:0", overlay,
        stdout=asyncio.subprocess.PIPE)).stdout.read())
    W, H = int(info["streams"][0]["width"]*scale), int(info["streams"][0]["height"]*scale)
    fc = f"[1:v]scale={W}:{H}[ov];[0:v][ov]overlay={x}:{y}"
    await run(["ffmpeg","-y","-i",base,"-i",overlay,
               "-filter_complex",fc,
               "-c:v","libx264","-preset","fast","-crf","23",
               "-c:a","aac","-b:a","128k","-shortest",out])

if __name__ == "__main__":
    op = sys.argv[1]
    args = sys.argv[2:]
    fn = {"join": op_join, "replace_audio": op_replace_audio,
          "text": op_text, "subs": op_subs, "pip": op_pip}[op]
    asyncio.run(fn(*args))
```

Использование:
```bash
python mini_ffmpeg_service.py join in1.mp4 in2.mp4 out.mp4
python mini_ffmpeg_service.py replace_audio video.mp4 voice.mp3 out.mp4
python mini_ffmpeg_service.py text video.mp4 "Hello" out.mp4
python mini_ffmpeg_service.py subs video.mp4 subs.srt out.mp4
python mini_ffmpeg_service.py pip base.mp4 overlay.mp4 out.mp4
```

## 10.11 Если язык не Python

Логика **не зависит от языка** — это всё shell‑команды:

- **Node.js:** `child_process.spawn('ffmpeg', args)`, парсить stderr через
  `Readable` events.
- **Go:** `exec.CommandContext(ctx, "ffmpeg", args...)`, `cmd.StderrPipe()` +
  `bufio.Scanner`.
- **Rust:** `tokio::process::Command::new("ffmpeg")`, async pipes.
- **Java/Kotlin:** `ProcessBuilder` + thread для stderr.

Заберите из этой документации:
1. Точные **аргументы FFmpeg** (см. 03–07, 10.5).
2. **Граф фильтров** для PiP/text/subtitles.
3. **Парсеры субтитров** (см. 09).
4. **Эскейпы** (drawtext text, concat path).

Остальное — код‑адаптер под ваш стек.

## 10.12 Что улучшить относительно оригинала

1. **`drawtext` escape**: `\\` должен быть **первым** в цепочке, иначе
   получаются двойные слеши вокруг уже эскейпленного.
2. **PiP `shadow=...` фильтр** — он не существует в стандартном FFmpeg.
   Заменить на `split` + `gblur` + `overlay` (см. 07.9).
3. **PiP `rounded` shape** — нестандартная формула в `geq`. Переписать
   на корректное расстояние до углового центра.
4. **`zoom_in/zoom_out` text animation** — фактически no‑op, реализовать
   через `scale` фильтр на общий слой.
5. **HW‑accel** — детект есть, но никто не использует. Добавить выбор в
   процессорах опционально.
6. **Кеш ffprobe** — есть в `VideoJoiner`, можно вынести в общий
   `MetadataCache` для всех процессоров.
7. **Два аудиотрека** в `audio_overlay` — добавить поддержку нескольких
   overlay (`amix=inputs=N`).

Все эти улучшения локальны — они не ломают публичный контракт API.
