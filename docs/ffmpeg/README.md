# Документация по функционалу FFmpeg

Эта папка содержит **полное и подробное** описание всего FFmpeg‑функционала
проекта `ffmpeg-api`. Цель — дать достаточно информации, чтобы повторить ту
же логику в другом проекте (на любом языке/фреймворке), сохранив поведение
оригинала.

Каждый документ описывает **отдельную операцию или подсистему**:
обоснование, схему запроса, валидацию, точные команды FFmpeg, структуру
фильтр‑графов, обработку прогресса, временных файлов и ошибок.

## Состав документации

| #  | Файл                                                       | Что описывает |
| -- | ---------------------------------------------------------- | ------------- |
| 01 | [01-overview.md](01-overview.md)                           | Общая архитектура: связь API → Celery → Processor → FFmpeg, состояния задачи, расширения файлов, окружение |
| 02 | [02-ffmpeg-core.md](02-ffmpeg-core.md)                     | Ядро: `FFmpegCommand` (run_command, get_video_info, get_audio_info, parse_progress), `FFmpegOptimizer`, `HardwareAccelerator`, `format_duration`, `parse_duration`, `parse_ffmpeg_output`, исключения |
| 03 | [03-video-join.md](03-video-join.md)                       | Объединение видео — `VideoJoiner`, concat demuxer, валидация совпадения разрешения/кодека/FPS, формат списка файлов |
| 04 | [04-audio-overlay.md](04-audio-overlay.md)                 | Наложение/замена аудио — `AudioOverlay` (режимы `replace` и `mix`), фильтр `amix`, `volume`, `-shortest`, смещение, обрезка |
| 05 | [05-text-overlay.md](05-text-overlay.md)                   | Наложение текста — `TextOverlay`, фильтр `drawtext`, 9 относительных позиций, фон/рамка/тень, 9 анимаций (fade/slide/zoom), экранирование |
| 06 | [06-subtitles.md](06-subtitles.md)                         | Субтитры — `SubtitleProcessor`, парсеры SRT/VTT/ASS/SSA, фильтр `subtitles`, `force_style`, генерация SRT из текста |
| 07 | [07-video-overlay-pip.md](07-video-overlay-pip.md)         | Picture‑in‑Picture — `VideoOverlay`, фильтр `overlay`, формы (rect/circle/rounded), border/shadow/opacity |
| 08 | [08-combined-pipeline.md](08-combined-pipeline.md)         | Pipeline комбинированных операций — `CombinedProcessor`, последовательное исполнение, передача результата между шагами |
| 09 | [09-utils-and-helpers.md](09-utils-and-helpers.md)         | Парсеры субтитров, работа с временными файлами, конвертация цвета, форматирование времени |
| 10 | [10-integration-guide.md](10-integration-guide.md)         | Гайд по реализации в другом проекте: зависимости, установка FFmpeg, шрифты, пример минимального CLI/сервиса |

## Соответствие исходникам

| Исходный код | Документ |
| ------------ | -------- |
| `app/ffmpeg/commands.py`               | 02 |
| `app/ffmpeg/utils.py`                  | 02, 09 |
| `app/ffmpeg/exceptions.py`             | 02 |
| `app/processors/base_processor.py`     | 01 |
| `app/processors/video_joiner.py`       | 03 |
| `app/processors/audio_overlay.py`      | 04 |
| `app/processors/text_overlay.py`       | 05 |
| `app/processors/subtitle_processor.py` | 06 |
| `app/processors/video_overlay.py`      | 07 |
| `app/processors/combined_processor.py` | 08 |
| `app/utils/subtitle_parsers.py`        | 06, 09 |
| `app/utils/temp_files.py`              | 09 |
| `app/schemas/*.py`                     | в каждом разделе |
| `app/queue/tasks.py`                   | 01 |
| `app/api/v1/tasks.py`                  | 01 |

## Как читать

1. **Начните с [01-overview.md](01-overview.md)** — там общая архитектура и
   жизненный цикл операции, без них остальные документы будут кусочными.
2. **Прочитайте [02-ffmpeg-core.md](02-ffmpeg-core.md)** — это слой, на котором
   построены все процессоры. Там же — оптимизация, hardware accel, парсинг
   прогресса.
3. **Дальше — по нужной операции**. Каждый из документов 03–08 — самостоятелен
   и содержит: входные параметры, валидацию, генерируемую команду FFmpeg,
   полные примеры, edge cases.
4. **При портировании** загляните в [10-integration-guide.md](10-integration-guide.md) —
   там сжатый чек‑лист и минимальные примеры на Python и shell.

## Краткая сводка операций

| Операция         | TaskType         | Endpoint               | Главный фильтр FFmpeg | Перекодировка |
| ---------------- | ---------------- | ---------------------- | --------------------- | ------------- |
| Объединение      | `join`           | `POST /tasks/join`           | `concat` demuxer      | Нет (`-c copy`) |
| Замена аудио     | `audio_overlay`  | `POST /tasks/audio-overlay`  | `-map`                | Только аудио (AAC) |
| Микс аудио       | `audio_overlay`  | `POST /tasks/audio-overlay`  | `amix`, `volume`      | Только аудио (AAC) |
| Текст            | `text_overlay`   | `POST /tasks/text-overlay`   | `drawtext`            | Видео (libx264 неявно) |
| Субтитры         | `subtitles`      | `POST /tasks/subtitles`      | `subtitles`           | Видео |
| Picture‑in‑Pic   | `video_overlay`  | `POST /tasks/video-overlay`  | `overlay` + `scale`   | Видео (libx264) |
| Pipeline         | `combined`       | `POST /tasks/combined`       | (несколько подряд)    | Зависит от шагов |

## Что нужно от системы

- **FFmpeg ≥ 4.4** (тестировалось на 4.4+) с поддержкой `libx264`, `libfreetype`
  (для `drawtext`), `libass` (для `subtitles`).
- **ffprobe** того же мажорного релиза — используется для метаданных.
- **Шрифты** (TTF) — `drawtext` принимает либо имя шрифта (если найден через
  fontconfig), либо путь к `.ttf`/`.otf`.
- **Достаточно места в `/tmp`** — для скачанных входных файлов и
  промежуточных результатов.
- (Опционально) `nvidia-smi` / `vainfo` — для авто‑детекта аппаратного
  ускорения (см. 02).

Все остальные технические детали — внутри отдельных документов.
