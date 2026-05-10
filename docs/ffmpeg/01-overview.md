# 01. Обзор архитектуры FFmpeg‑функционала

## Высокоуровневая схема

```
┌─────────────┐    ┌────────────┐    ┌─────────────┐    ┌────────┐
│ HTTP Client │───►│ FastAPI    │───►│ Celery       │───►│ FFmpeg │
│             │    │ /tasks/*   │    │ task (worker)│    │ subproc│
└─────────────┘    └────────────┘    └─────────────┘    └────────┘
                          │                  │
                          ▼                  ▼
                   ┌──────────────────────────────┐
                   │ MinIO (S3) + PostgreSQL      │
                   │ файлы, метаданные, статус    │
                   └──────────────────────────────┘
```

Фактический поток для любой задачи:

1. Клиент загружает файлы (`POST /files/upload`) — они сохраняются в **MinIO**,
   метаданные о них — в **PostgreSQL** (таблица `files`).
2. Клиент создает задачу (`POST /tasks/<тип>`), передавая ID файлов и
   конфигурацию операции. API создает запись в `tasks` и ставит Celery‑задачу.
3. Celery‑воркер берет задачу, **скачивает** входные файлы из MinIO во
   временную директорию, конструирует объект Processor и запускает его.
4. Processor собирает аргументы FFmpeg, вызывает `ffmpeg`/`ffprobe`,
   парсит stderr для прогресса, обновляет `tasks.progress` в БД.
5. Готовый файл загружается обратно в MinIO, регистрируется в `files`,
   `tasks.status` ставится в `completed`.

## Карта файлов

```
app/
├── ffmpeg/
│   ├── commands.py     # FFmpegCommand: запуск, ffprobe, прогресс
│   │                   # FFmpegOptimizer: preset/tune/crf/threads
│   │                   # HardwareAccelerator: nvenc/qsv/vaapi
│   ├── exceptions.py   # FFmpegError, FFmpegValidationError, ...
│   └── utils.py        # parse_duration, format_duration, parse_ffmpeg_output
├── processors/
│   ├── base_processor.py        # BaseProcessor (ABC) — validate→process→cleanup
│   ├── video_joiner.py          # concat demuxer
│   ├── audio_overlay.py         # replace / mix audio
│   ├── text_overlay.py          # drawtext + animations
│   ├── subtitle_processor.py    # subtitles фильтр
│   ├── video_overlay.py         # PiP (overlay фильтр)
│   └── combined_processor.py    # pipeline нескольких операций
├── schemas/                     # Pydantic — валидация запросов
│   ├── audio_overlay.py
│   ├── text_overlay.py
│   ├── subtitle.py
│   ├── video_overlay.py
│   └── combined.py
├── utils/
│   ├── subtitle_parsers.py      # SRT/VTT/ASS/SSA → list[dict]
│   └── temp_files.py            # create_temp_file, create_temp_dir, cleanup
├── queue/
│   ├── celery_app.py            # Celery + brokerset, time limits
│   └── tasks.py                 # @celery_app.task: одна функция на тип задачи
└── api/v1/tasks.py              # FastAPI endpoints, превращают тело запроса
                                 # в config + task.delay(...)
```

## Контракт `BaseProcessor`

Все процессоры наследуют один и тот же ABC (`app/processors/base_processor.py`):

```python
class BaseProcessor(ABC):
    def __init__(self, task_id, config, progress_callback=None):
        self.task_id = task_id
        self.config = config            # dict — все параметры операции
        self.progress_callback = progress_callback   # вызывается с 0.0–100.0
        self.temp_files: list[str] = []

    @abstractmethod
    async def validate_input(self) -> None: ...

    @abstractmethod
    async def process(self) -> dict: ...

    async def run(self) -> dict:
        await self.validate_input()
        try:
            return await self.process()
        finally:
            await self.cleanup()

    async def cleanup(self):
        for path in self.temp_files:
            try: os.remove(path)
            except OSError: pass
        self.temp_files.clear()

    def update_progress(self, p: float):
        if self.progress_callback:
            self.progress_callback(p)

    def add_temp_file(self, p: str):
        self.temp_files.append(p)
```

Все процессоры ведут себя одинаково:
- `validate_input()` — поднимает `FFmpegValidationError` (см. 02), если данные
  некорректны или файлы недоступны.
- `process()` — собирает FFmpeg‑команду, запускает, возвращает
  `{"output_path": "/tmp/...mp4"}`.
- `cleanup()` — гарантированно удаляет все промежуточные файлы из
  `self.temp_files` (даже при исключении в `process`).
- `update_progress(p)` — пробрасывает прогресс наверх (Celery → запись в БД).

## Жизненный цикл задачи (Celery worker)

Все Celery‑задачи в `app/queue/tasks.py` устроены одинаково:

```python
@celery_app.task(
    bind=True, max_retries=3, default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True, retry_backoff_max=300, retry_jitter=True,
)
def some_task(self, task_id: int, config: dict) -> dict:
    db = get_db_sync()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task.status == TaskStatus.CANCELLED:
            return {"status": "cancelled"}
        task.status = TaskStatus.PROCESSING
        task.progress = 0.0
        db.commit()

        # 1) Скачиваем все входные файлы из MinIO в /tmp
        # 2) Готовим processor_config (видео_path, audio_path, ...)
        # 3) Создаем Processor с progress_callback, который пишет в БД
        # 4) result = asyncio.run(processor.run())
        # 5) Загружаем результат в MinIO, создаем запись File,
        #    обновляем task.output_files и task.result.

        task.status = TaskStatus.COMPLETED
        task.progress = 100.0
        task.completed_at = datetime.utcnow()
        db.commit()
        return {"output_file_id": new_file.id, "status": "completed"}
    except PermanentError as e:
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        db.commit()
        raise
    except Exception as e:
        task.status = TaskStatus.FAILED
        task.error_message = str(e)
        db.commit()
        if isinstance(e, TemporaryError):
            raise self.retry(exc=e)
        raise
    finally:
        # Удаляем скачанные локальные файлы и temp_dir
        db.close()
```

Два специальных типа исключений:
- `PermanentError` — данные/состояние не позволят успешно обработать
  (нет файла, разные кодеки и т.п.). **Не повторять.**
- `TemporaryError` — сеть/MinIO/timeout. **Повторить с backoff.**

## Состояния задачи

```python
class TaskStatus(str, Enum):
    PENDING    = "pending"     # в очереди
    PROCESSING = "processing"  # FFmpeg работает
    COMPLETED  = "completed"   # ОК, output_files заполнено
    FAILED     = "failed"      # error_message заполнен
    CANCELLED  = "cancelled"   # отменена пользователем
```

```python
class TaskType(str, Enum):
    JOIN          = "join"
    AUDIO_OVERLAY = "audio_overlay"
    TEXT_OVERLAY  = "text_overlay"
    SUBTITLES     = "subtitles"
    VIDEO_OVERLAY = "video_overlay"
    COMBINED      = "combined"
```

## Поддерживаемые форматы (из конфигурации, `app/config.py`)

```python
ALLOWED_VIDEO_EXTENSIONS    = ["mp4", "avi", "mov", "mkv", "wmv"]
ALLOWED_AUDIO_EXTENSIONS    = ["mp3", "aac", "wav", "flac", "ogg"]
ALLOWED_SUBTITLE_EXTENSIONS = ["srt", "vtt", "ass", "ssa"]
```

Выходной формат всегда **MP4** (H.264 + AAC), это зашито в процессорах
(см. отдельные документы — где `libx264`/`-c:v copy`/`aac`).

## Прогресс

`FFmpegCommand.run_command(...)` стримит stderr и вызывает
`progress_callback` со значением 0–100% (если задана общая длительность).
Парсер ищет в stderr строку `time=HH:MM:SS.xx` (см.
`FFmpegCommand.parse_ffmpeg_progress`).

В Celery‑задаче `progress_callback` коммитит `task.progress` в БД на каждое
обновление. На фронтенде клиент опрашивает `GET /tasks/{id}` и видит
`progress: 47.3` и т.д.

## Таймауты

- **Дефолтный таймаут команды FFmpeg** — 3600 c (1 час). Передается через
  `config["timeout"]`, берется из `settings.TASK_TIMEOUT`.
- **Celery hard time limit** — `CELERY_TASK_TIME_LIMIT` (по умолчанию 3600).
- **Celery soft time limit** — `CELERY_TASK_SOFT_TIME_LIMIT` (по умолчанию 3000).
- При таймауте FFmpeg `run_command` отправляет `proc.kill()` и поднимает
  `FFmpegTimeoutError`.

## Что НЕ входит в FFmpeg‑слой (важно при портировании)

- **Хранилище файлов** (MinIO/S3) — отделено от процессоров. Они работают
  только с локальными путями `/tmp/...`. Скачать/загрузить — задача вызывающего
  кода (в текущем коде — Celery‑задачи).
- **Аутентификация / БД / api** — не имеют отношения к самим FFmpeg‑операциям.
- **Очередь** — Celery, но в другом проекте можно использовать что угодно
  (RQ, ARQ, BullMQ, голый thread‑pool). Процессоры — обычные async‑классы.

## Минимально необходимое окружение

| Что              | Как используется             | Где задается           |
| ---------------- | ---------------------------- | ---------------------- |
| `ffmpeg` бинарь  | `FFMPEG_PATH` (default `ffmpeg`) | `app/config.py` → `Settings.FFMPEG_PATH` |
| `ffprobe` бинарь | `FFPROBE_PATH` (default `ffprobe`)| `app/config.py` → `Settings.FFPROBE_PATH` |
| `/tmp` writable  | временные файлы              | `tempfile.mkstemp` в `app/utils/temp_files.py` |
| Шрифты           | `drawtext` ищет через fontconfig | передается имя в фильтр (см. 05) |
| `libass`         | для `subtitles` фильтра      | должен быть собран в FFmpeg |

## Дальше

Перейдите к [02-ffmpeg-core.md](02-ffmpeg-core.md) — там подробно описана
сама обертка над FFmpeg, на которой стоят все процессоры.
