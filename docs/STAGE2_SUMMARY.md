# Этап 2: Основной функционал — итог реализации

## Выполненные подзадачи

### 2.1 Очередь задач (Celery)
- **app/queue/celery_app.py** — приложение Celery (broker/backend из настроек, include tasks и periodic_tasks).
- **app/queue/beat_schedule.py** — расписание Beat: очистка старых файлов каждый час, временных — каждые 30 мин.
- **app/schemas/task.py** — схемы TaskCreate, TaskUpdate, TaskResponse, TaskListResponse (TaskType, TaskStatus из моделей).
- **app/services/task_service.py** — TaskService: create_task, get_task, get_tasks, cancel_task, retry_task, update_status, update_progress, update_result.
- В модель **Task** добавлено поле **priority** (int, default 5). Миграция: `alembic/versions/20250205_add_task_priority.py`.

### 2.2 Загрузка файлов
- **app/storage/minio_client.py** — MinIOClient: upload_file, upload_bytes, download_file, get_file_url, delete_file, file_exists, get_file_info (sync Minio в asyncio.to_thread).
- **app/schemas/file.py** — FileMetadata, FileUploadResponse, FileInfo, FileListResponse, UploadFromUrlRequest.
- **app/services/file_service.py** — FileService: validate_file, upload_from_request, upload_from_url, get_file_info, get_user_files, delete_file, download_file, get_download_url.
- **app/api/v1/files.py** — эндпоинты: POST /upload, POST /upload-url, GET /{file_id}, GET /{file_id}/download, DELETE /{file_id}, GET / (список с пагинацией).

### 2.3 FFmpeg базовый процессор
- **app/ffmpeg/exceptions.py** — FFmpegError, FFmpegValidationError, FFmpegProcessingError, FFmpegTimeoutError.
- **app/ffmpeg/utils.py** — format_duration, parse_duration, parse_ffmpeg_output, get_file_metadata.
- **app/ffmpeg/commands.py** — FFmpegCommand: run_command, get_video_info, get_audio_info, validate_file, parse_ffmpeg_progress.
- **app/utils/temp_files.py** — create_temp_file, create_temp_dir, cleanup_temp_files, cleanup_old_files.
- **app/processors/base_processor.py** — BaseProcessor: validate_input, process, run, cleanup, update_progress, add_temp_file.

### 2.4 Объединение видео (Join)
- **app/processors/video_joiner.py** — VideoJoiner: validate_input (≥2 файлов, совпадение разрешения/FPS/кодека), _create_concat_list, _generate_ffmpeg_command, process (concat demuxer, -c copy).
- **app/queue/tasks.py** — join_video_task (Celery): скачивание из MinIO, VideoJoiner, загрузка результата в MinIO, обновление задачи и output_files.
- **app/api/v1/tasks.py** — POST /tasks/join (body: file_ids, output_filename), проверка прав на файлы, создание задачи и вызов join_video_task.delay().

### 2.5 Task management
- **app/queue/signals.py** — обработчики task_prerun (PROCESSING), task_postrun (completed_at), task_failure (FAILED + error_message), task_success (COMPLETED + result).
- **app/api/v1/tasks.py** — POST /tasks (общее создание), GET /tasks (фильтры status, type, пагинация), GET /tasks/{task_id}, POST /tasks/{task_id}/cancel, POST /tasks/{task_id}/retry.

## Запуск

1. Установить зависимости: `pip install -r requirements.txt`
2. Применить миграцию для поля priority: `alembic upgrade head` (если БД уже есть и таблица tasks создана без priority).
3. Redis и MinIO должны быть доступны (см. docker-compose).
4. Запуск worker: `celery -A app.queue.celery_app worker -l info`
5. Запуск beat (по желанию): `celery -A app.queue.celery_app beat -l info`
6. API: `uvicorn app.main:app --reload`

## Примечания

- В репозитории задач при создании передаются `input_files` и `output_files` как списки (в БД хранятся в JSON).
- Join-задача проверяет принадлежность файлов пользователю перед созданием задачи и в воркере при скачивании.
- Для работы join воркер должен иметь доступ к БД (sync через get_db_sync), MinIO и FFmpeg в PATH.
