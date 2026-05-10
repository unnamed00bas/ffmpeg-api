# 08. Pipeline комбинированных операций — `CombinedProcessor`

> **Источник:** `app/processors/combined_processor.py`, `app/schemas/combined.py`,
> `app/queue/tasks.py:combined_task`, `app/api/v1/tasks.py:create_combined_task`.

## 8.1 Назначение

Выполнить **последовательность** операций в едином запросе. Каждый шаг
получает на вход результат предыдущего, и таким образом за один POST можно,
например:

1. Склеить 3 видео.
2. Наложить субтитры.
3. Заменить аудио.
4. Добавить логотип (PiP).

Текущая реализация ограничена: **2–10 операций** в одной задаче.

## 8.2 Эндпоинт API

```
POST /api/v1/tasks/combined
{
  "base_file_id": 123,
  "operations": [
    {
      "type": "join",
      "config": { "file_ids": [124, 125] }
    },
    {
      "type": "subtitles",
      "config": {
        "subtitle_text": [{"start":0,"end":3,"text":"Title"}],
        "format": "SRT"
      }
    },
    {
      "type": "audio_overlay",
      "config": {
        "audio_file_id": 130,
        "mode": "replace"
      }
    },
    {
      "type": "video_overlay",
      "config": {
        "overlay_video_file_id": 200,
        "config": {"x": 20, "y": 20, "scale": 0.2}
      }
    }
  ],
  "output_filename": "result.mp4"
}
```

## 8.3 Pydantic‑схемы

```python
class OperationType(str, Enum):
    JOIN          = "join"
    AUDIO_OVERLAY = "audio_overlay"
    TEXT_OVERLAY  = "text_overlay"
    SUBTITLES     = "subtitles"
    VIDEO_OVERLAY = "video_overlay"

class Operation(BaseModel):
    type:   OperationType
    config: Dict[str, Any] = {}

class CombinedRequest(BaseModel):
    operations:      List[Operation] = Field(..., min_length=2, max_length=10)
    base_file_id:    FileSource
    output_filename: Optional[str] = None
```

## 8.4 Конфигурация процессора

```python
config = {
    "base_file_id":    123,
    "operations":      [{"type": "...", "config": {...}}, ...],
    "output_filename": "result.mp4",
    "user_id":         <int>,         # для записи File в БД
    "timeout":         3600,
}
```

## 8.5 Валидация

`validate_input()`:
1. `2 ≤ len(operations) ≤ 10`.
2. `base_file_id` — целое.
3. Каждая операция: `type` ∈ `{join, audio_overlay, text_overlay, subtitles, video_overlay}`.
4. Каждая операция: `config` — словарь.

## 8.6 Алгоритм исполнения (`process()`)

```
1) load(base_file_id) → /tmp/input_<id>_<name>          ← current_file
2) for op in operations:
       progress = (i / N) * 100
       update_progress(progress)
       result_file = _execute_operation(op, current_file)
       remove(current_file)             # старый промежуточный — сразу удаляем
       current_file = result_file        # становится входом следующей операции
3) update_progress(100)
4) result_file_id = _upload_result(current_file)
5) return {"result_file_id": ..., "operations_count": N}
```

При исключении в любом шаге вызывается `_rollback()` (= `cleanup()`) —
удаляются все временные и промежуточные файлы, ошибка пробрасывается.

## 8.7 Подготовка конфигурации каждого шага

`_prepare_processor_config(processor, op_type, op_cfg, input_file)` —
**ключевое место**, где результат предыдущего шага «вшивается» в конфиг
следующего. Маппинг:

| `op_type`        | Что пишется в `op_cfg` |
| ---------------- | ----------------------- |
| `join`           | `op_cfg["input_paths"] = [input_file] + op_cfg.get("secondary_input_paths", [])` |
| `audio_overlay`  | `op_cfg["video_path"]   = input_file` |
| `text_overlay`   | `op_cfg["video_path"]   = input_file` |
| `subtitles`      | `op_cfg["video_path"]   = input_file` |
| `video_overlay`  | `op_cfg["base_file_path"] = input_file` |

То есть **каждый процессор** ожидает входной файл под своим именем
(см. соответствующие документы 03–07), и `CombinedProcessor` подставляет
текущий файл в нужный ключ.

Для операций, которые требуют **дополнительные** файлы (audio_overlay,
video_overlay, subtitles, join), эти файлы должны быть **уже скачаны и
подложены** в config заранее (см. 8.8).

## 8.8 Препроцесс файлов в Celery‑задаче (`combined_task`)

В `app/queue/tasks.py` Celery‑задача **до** запуска процессора:

```python
for op in operations:
    if op.type == "join" and "file_ids" in op.config:
        # скачать каждый, заполнить op["config"]["secondary_input_paths"]
    elif op.type == "video_overlay" and "overlay_video_file_id" in op.config:
        # скачать, заполнить op["config"]["overlay_file_path"]
    elif op.type == "audio_overlay" and "audio_file_id" in op.config:
        # скачать, заполнить op["config"]["audio_path"]
    elif op.type == "subtitles" and "subtitle_file_id" in op.config:
        # скачать, заполнить op["config"]["subtitle_file_path"]
```

Все скачанные пути добавляются в `local_resource_paths` и удаляются в `finally`.

> При портировании важно сохранить эту схему: процессоры **не работают с
> file_id** напрямую (за исключением `_load_file/_upload_result` в
> `CombinedProcessor`, см. 8.9). Оркестратор обязан подготовить пути.

## 8.9 Загрузка/выгрузка файлов внутри `CombinedProcessor`

Это **исключение** в общем правиле: `CombinedProcessor` сам обращается
к MinIO и БД:

- `_load_file(file_id)` — читает `File` из PostgreSQL, скачивает из MinIO во
  временный файл, возвращает путь.
- `_upload_result(file_path)` — загружает в MinIO, создает запись `File` для
  текущего пользователя, возвращает `id`.

При портировании этот слой можно унести наверх (в Celery‑задачу), как
сделано во всех остальных процессорах (`VideoJoiner`, `AudioOverlay`, ...).
Тогда `CombinedProcessor` станет «чистым» оркестратором.

## 8.10 Пример полного цикла

Предположим:
- base = `intro.mp4`,
- операция 1: `join` с `file_ids=[main.mp4, outro.mp4]` →
  `joined.mp4` (intro+main+outro),
- операция 2: `subtitles` с `subtitle_text` → `subtitled.mp4`,
- операция 3: `audio_overlay`, `mode=replace` с music.mp3 → `final.mp4`.

Прогресс задачи:
```
0%   — старт
33%  — после join
66%  — после subtitles
100% — после audio_overlay
```

Между шагами в `/tmp` живут только текущий и следующий файлы — старые
удаляются сразу после успешного шага.

## 8.11 Создание процессоров (динамический импорт)

`_create_processor(op_type, op_config)`:

```python
processors_map = {
    "audio_overlay": ("app.processors.audio_overlay",   "AudioOverlay"),
    "text_overlay":  ("app.processors.text_overlay",    "TextOverlay"),
    "subtitles":     ("app.processors.subtitle_processor", "SubtitleProcessor"),
    "video_overlay": ("app.processors.video_overlay",   "VideoOverlay"),
}
# Для join — отдельная ветка (импорт VideoJoiner).
```

`importlib.import_module` + `getattr` — чтобы тип `Combined` можно было
расширять, не редактируя сам процессор.

## 8.12 Извлечение output (`_extract_output_file`)

Каждый процессор возвращает dict с одним из ключей:

```python
possible_keys = ["output_path", "output_file", "result_file"]
```

`CombinedProcessor` берет первый существующий ключ, проверяет существование
файла на диске. Иначе — `FFmpegValidationError`.

## 8.13 Очистка (`cleanup`)

Кроме `BaseProcessor.cleanup()` (`temp_files`), `CombinedProcessor`
дополнительно удаляет `intermediate_files` (все промежуточные результаты,
которые он отслеживает отдельно).

## 8.14 Edge cases

| Ситуация | Поведение |
| -------- | --------- |
| `len(operations) < 2` | `FFmpegValidationError("At least 2 operations required ...")` |
| `len(operations) > 10` | `FFmpegValidationError("Maximum 10 operations allowed")` |
| `type` неизвестен | `FFmpegValidationError("Invalid operation type ...")` |
| Неверный formatter `op["config"]` (не dict) | `FFmpegValidationError("Operation config must be a dictionary ...")` |
| Шаг бросает любое исключение | `_rollback()` (cleanup), исключение пробрасывается, задача в `failed` |
| `join` стоит **не первой** операцией | Технически разрешено: `input_paths = [current_file] + secondary_input_paths`, то есть текущий файл будет первым. Это нормально работает. |
| Операция **изменяет разрешение** (subtitles/text — нет, video_overlay — нет) | join после video_overlay сломается, если разрешения разойдутся. Учитывайте порядок. |
| Промежуточные файлы — большие | удаляются сразу после следующего успешного шага, диск не растет линейно с числом шагов |

## 8.15 Реализация без MinIO/PostgreSQL (для портирования)

Если нет файлового хранилища и БД, оркестратор сводится к простому
циклу по локальным путям:

```python
async def run_pipeline(base_path, operations, out_path):
    current = base_path
    intermediates = []
    try:
        for op in operations:
            proc = build_processor(op["type"], {
                **op["config"],
                # подставляем current под нужным ключом:
                **(  {"video_path":      current} if op["type"] in
                     {"audio_overlay","text_overlay","subtitles"} else
                     {"base_file_path": current} if op["type"] == "video_overlay" else
                     {"input_paths":   [current] + op["config"].get("secondary_input_paths",[])}
                     if op["type"] == "join" else {}
                ),
            })
            await proc.validate_input()
            res = await proc.process()
            new_path = res["output_path"]
            if current != base_path:    # base не удаляем
                os.remove(current)
            intermediates.append(new_path)
            current = new_path
        os.replace(current, out_path)   # финальный → out_path
    except Exception:
        for p in intermediates:
            if os.path.exists(p): os.remove(p)
        raise
```

## 8.16 Что важно при отладке

- Каждый шаг — отдельный вызов `ffmpeg`. Если хотите дебажить — логируйте
  `command` каждого шага.
- В реальном проекте Celery‑задача коммитит `task.progress` в БД на каждое
  обновление — но **в `CombinedProcessor` `progress_callback=None`** для
  внутренних подпроцессоров. Прогресс считается только по «крупным шагам»
  (i/N). Если хотите детальный — пробрасывайте свой callback в
  `_create_processor`.
- Обратите внимание: `_load_file` и `_upload_result` используют
  `get_db_sync()` и `MinIOClient` — синхронные клиенты внутри async‑метода.
  В тестах/портировании это часто заменяется на чисто файловое API.
