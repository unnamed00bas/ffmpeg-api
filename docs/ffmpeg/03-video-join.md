# 03. Объединение видео — `VideoJoiner`

> **Источник:** `app/processors/video_joiner.py`, `app/queue/tasks.py:join_video_task`,
> `app/api/v1/tasks.py:create_join_task`.

## 3.1 Назначение

Склейка ≥ 2 видео в одно. Используется **concat demuxer** FFmpeg c `-c copy`,
то есть **без перекодирования**. Это очень быстро (буквально перепаковка
TS/PES/MOV‑чанков), но требует, чтобы видео имели **одинаковые** параметры:
кодек, разрешение, FPS.

## 3.2 Эндпоинт API

```
POST /api/v1/tasks/join
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "file_ids": [123, 456, "https://example.com/clip3.mp4"],
  "output_filename": "joined.mp4",
  "priority": 5
}
```

Поле `file_ids` принимает **либо int (id уже загруженного файла)**,
**либо строку‑URL** (тогда файл будет автоматически зарегистрирован/скачан).

Минимум 2 файла. Все файлы должны принадлежать пользователю.

Ответ — `TaskResponse` с `status: "pending"` и `id` задачи.

## 3.3 Конфигурация процессора

`VideoJoiner.__init__(task_id, config, progress_callback=None, cache_service=None)`:

```python
config = {
    "input_paths": ["/tmp/.../v1.mp4", "/tmp/.../v2.mp4", ...],  # обязательно
    "file_ids":   [123, 456, ...],          # опционально, для кеша
    "output_path": "/tmp/.../joined.mp4",   # если нет — создается tmp
    "optimization": {                        # опционально
        "scenario": "fast" | "balanced" | "quality" | None
    },
    "timeout": 3600,                         # секунд
}
```

`cache_service` — если передан, будут использоваться:
- `VideoMetadataCache` — кеширование результата ffprobe по `(file_id, path)`.
- `OperationResultCache` — кеширование самого результата операции
  (по типу `"join"`, `file_ids`, `config`).

В Celery‑задаче кеш не передается (см. `tasks.py:join_video_task`), но
интерфейс готов.

## 3.4 Валидация — `validate_input()`

Бросает `FFmpegValidationError`, если:
1. `len(input_paths) < 2`.
2. У любого второго+ видео отличаются:
   - **разрешение** (`width`, `height`),
   - **видеокодек** (`video_codec`),
   - **FPS** (отличие > 0.1, если оба заданы).

Метаданные берутся через `FFmpegCommand.get_video_info(path)` — то есть
вызывается `ffprobe`. При наличии `cache_service` сначала смотрится кеш.

> Если разрешения/FPS отличаются — нужно **сначала перекодировать** все клипы
> в единый формат (это вне области `VideoJoiner`). Самый простой способ —
> прогнать каждый через `ffmpeg -vf scale=1920:1080,fps=30 -c:v libx264 ...`
> и потом склеить. В текущем коде такой автоматики нет.

## 3.5 Команда FFmpeg

### Шаг 1. Создание concat‑списка

`_create_concat_list(video_files)`:
1. Создает временную директорию (`create_temp_dir()`).
2. Создает в ней файл `concat_<hex>.txt`.
3. Записывает в него по одной строке на каждый файл:
   ```
   file '/tmp/.../v1.mp4'
   file '/tmp/.../v2.mp4'
   file '/tmp/.../v3.mp4'
   ```
4. **Экранирование одинарных кавычек:** в путях `'` заменяется на `'\''`
   (POSIX‑шеллный escape, который понимает concat demuxer).

> Это критическое место. Если в имени файла встречается одинарная кавычка
> (например, `My Movie's clip.mp4`) и не сделать escape, FFmpeg выдаст
> «`Failed to avoid negative pts`» или просто отвалится. Используется
> подстановка `path.replace("'", "'\\''")`.

### Шаг 2. Запуск FFmpeg

```
ffmpeg -y \
  -f concat -safe 0 \
  -i /tmp/.../concat_xxx.txt \
  -c copy \
  /tmp/.../joined.mp4
```

Ключи:

| Ключ                | Зачем |
| ------------------- | ----- |
| `-y`                | перезаписать выход без вопроса |
| `-f concat`         | использовать concat demuxer |
| `-safe 0`           | разрешить произвольные пути в списке (по умолчанию запрещены абсолютные) |
| `-i <list>`         | путь к concat‑файлу |
| `-c copy`           | копировать потоки без перекодирования |

### Сценарии оптимизации

В `_generate_ffmpeg_command(...)` есть ветка для `config["optimization"]["scenario"]` —
она конструирует `FFmpegOptimizer` с пресетом, но при `-c copy` параметры
кодирования **не применяются**. Это «задел» на режим перекодирования.

## 3.6 Прогресс

`VideoJoiner.process()`:
1. До запуска FFmpeg суммирует длительности всех `input_paths` через
   `get_video_info` → `total_duration`.
2. Передает `progress_callback`, который пересчитывает время из stderr в
   процент: `100 * current / total_duration`.

При совсем коротких склейках callback может не успеть сработать ни разу —
итоговый `update_progress(100.0)` гарантирован после возврата FFmpeg.

## 3.7 Что возвращает `process()`

```python
return {"output_path": "/tmp/.../joined.mp4"}
```

Дальше Celery‑задача (`join_video_task`) загружает этот файл в MinIO,
создает запись `File(user_id, filename, original_filename, size,
content_type='video/mp4', storage_path=object_name)` и пишет
`task.result = {"output_file_id": new_file.id, "object_name": object_name}`.

## 3.8 Полный пример воспроизведения вручную

```bash
# Допустим, есть три клипа одинакового формата:
echo "file 'in1.mp4'" >  list.txt
echo "file 'in2.mp4'" >> list.txt
echo "file 'in3.mp4'" >> list.txt

ffmpeg -y -f concat -safe 0 -i list.txt -c copy out.mp4
```

Если разрешения/кодеки отличаются — concat demuxer молча произведет
«битый» MP4 (рассинхрон или артефакты). Поэтому валидация в процессоре
обязательна.

## 3.9 Edge cases / частые проблемы

| Симптом | Причина | Решение |
| ------- | ------- | ------- |
| `Failed to avoid negative pts`, рассинхрон A/V | разные кодеки/разрешения/FPS | перекодировать перед concat |
| FFmpeg падает с «Unsafe file name» | `-safe 0` не передан | оставить `-safe 0` всегда |
| concat demuxer берет только первый файл | в списке нет переноса между записями | `\n` между `file '...'` строками |
| Все файлы одинаковые, но FPS показан как `30000/1001` ≈ 29.97 vs `30/1` | разные `r_frame_rate` | сравнивать с допуском (тут — 0.1) |
| Кириллица в путях | в Linux обычно ОК (UTF‑8 локаль); на Windows — нужен короткий ASCII‑путь или `chcp 65001` | избегать «странных» путей |

## 3.10 Альтернатива: concat protocol vs filter

Concat demuxer (используется в проекте) — самый универсальный способ.
Альтернативы:

- **Concat protocol** (`concat:in1.mp4|in2.mp4`) — работает только для MPEG‑TS.
- **Concat filter** (`-filter_complex 'concat=n=3:v=1:a=1'`) — требует
  перекодирования, но позволяет склеивать клипы с разными форматами.
  Это **не используется** в `VideoJoiner`, но это путь, если нужно
  поддержать смешанные входы.

## 3.11 Минимальная реализация на чистом Python

```python
import asyncio, os, tempfile
from app.ffmpeg.commands import FFmpegCommand   # либо своя обертка

async def join_videos(paths: list[str], out: str, ffmpeg="ffmpeg"):
    if len(paths) < 2:
        raise ValueError("need ≥2")
    # 1) валидация — пропускаем для краткости
    # 2) concat list
    fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="concat_")
    os.close(fd)
    with open(list_path, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{p.replace(chr(39), chr(39)+chr(92)+chr(39)+chr(39))}'\n")
    try:
        await FFmpegCommand.run_command([
            ffmpeg, "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            out,
        ])
    finally:
        os.remove(list_path)
    return out
```
