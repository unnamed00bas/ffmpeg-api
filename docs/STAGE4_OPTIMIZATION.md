# Оптимизация FFmpeg

## FFmpegOptimizer

**Модуль:** `app/ffmpeg/commands.py`

### Параметры кодирования

- **FFmpegPreset**: пресеты кодирования (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow).
- **FFmpegTune**: тюнинг под контент (film, animation, grain, stillimage, fastdecode, zerolatency).
- **CRF** (Constant Rate Factor): управление качеством (меньше = лучше качество, больше размер).
- **Threads**: количество потоков.

### Сценарии оптимизации

Метод `FFmpegOptimizer.optimize_for_scenario(scenario)`:
- **fast**: preset=veryfast, tune=fastdecode, threads=4.
- **balanced**: preset=fast, tune=film, threads=4.
- **quality**: preset=medium, tune=film, crf=18, threads=4.

### Hardware Acceleration

**Класс:** `HardwareAccelerator`

Методы:
- `detect_available()`: обнаруживает nvenc (NVIDIA), vaapi (Linux), qsv (Intel).
- `get_hwaccel_params(accelerator)`: возвращает параметры FFmpeg для выбранного ускорителя.

Примеры параметров:
- nvenc: `-hwaccel cuda -c:v h264_nvenc`
- qsv: `-hwaccel qsv -c:v h264_qsv`
- vaapi: `-hwaccel vaapi -vaapi_device /dev/dri/renderD128 -c:v h264_vaapi`

### Интеграция в процессоры

Пример интеграции в `VideoJoiner` (`app/processors/video_joiner.py`):

```python
from app.ffmpeg.commands import FFmpegOptimizer, FFmpegPreset, FFmpegTune
from app.cache.cache_service import CacheService, VideoMetadataCache, OperationResultCache

class VideoJoiner(BaseProcessor):
    def __init__(self, task_id, config, progress_callback=None, cache_service=None):
        super().__init__(task_id, config, progress_callback)
        self.cache_service = cache_service
        self.video_metadata_cache = VideoMetadataCache(cache_service) if cache_service else None
        self.operation_result_cache = OperationResultCache(cache_service) if cache_service else None

    async def process(self):
        # Кэш результата
        if self.operation_result_cache:
            cached = await self.operation_result_cache.get_result(
                "join",
                self.config.get("file_ids") or [],
                self.config
            )
            if cached:
                self.update_progress(100)
                return cached

        # Получение метаданных с кэшем
        file_metadata = []
        for file_id, file_path in zip(
            self.config.get("file_ids") or [],
            self.config.get("input_paths") or []
        ):
            if self.video_metadata_cache:
                info = await self.video_metadata_cache.get_video_info(file_id, file_path)
                if info:
                    file_metadata.append(info)
                    continue
            info = await FFmpegCommand.get_video_info(file_path)
            file_metadata.append(info)
            if self.video_metadata_cache:
                await self.video_metadata_cache.set_video_info(file_id, file_path, info)

        # Генерация команды (параметры оптимизации игнорируются для concat demuxer,
        # но можно добавить при необходимости кодирования)
        result = await self._process_join(file_metadata)

        # Сохранение в кэш
        if self.operation_result_cache:
            await self.operation_result_cache.set_result(
                "join",
                self.config.get("file_ids") or [],
                self.config,
                result
            )
        return result
```

---

# Кэширование

## CacheService

**Модуль:** `app/cache/cache_service.py`

### Методы

- `get(key)`: получение значения из кэша (десериализация JSON).
- `set(key, value, ttl)`: сохранение с TTL (по умолчанию 1 час).
- `delete(key)`: удаление ключа.
- `clear()`: очистка текущей БД Redis.
- `exists(key)`: проверка существования.
- `generate_key(prefix, **kwargs)`: детерминированный ключ по параметрам.

### VideoMetadataCache

Кэш метаданных видео (ffprobe):
- TTL: 24 часа.
- Ключ: `video:info:{file_id}:{md5(file_path)}`.
- Методы: `get_video_info`, `set_video_info`, `invalidate`.

### OperationResultCache

Кэш результатов операций:
- TTL: 7 дней.
- Ключ: `operation:result:{md5(type,file_ids=sorted&config=sorted)}`.
- Методы: `get_result`, `set_result`.

---

# Стриминг больших файлов

## Chunked Upload

**Сервис:** `app/services/chunk_upload.py`

### Эндпоинты

- `POST /files/upload-init`: создание сессии загрузки, возврат `upload_id`.
- `POST /files/upload-chunk/{upload_id}/{chunk_number}`: загрузка чанка в MinIO.
- `POST /files/upload-complete/{upload_id}`: сборка чанков, загрузка в MinIO, создание записи File.
- `POST /files/upload-abort/{upload_id}`: отмена, удаление чанков и Redis-записи.

### Поток работы

1. Клиент вызывает `/upload-init` с filename, total_size, total_chunks, content_type → `upload_id`.
2. Клиент загружает чанки по одному на `/upload-chunk/{upload_id}/{n}` → чанки в MinIO `temp/chunks/`.
3. После загрузки всех чанков → `/upload-complete` → сборка во временный файл, загрузка в MinIO, запись в БД.
4. При прерывании → `/upload-abort` → удаление чанков.

## Range Download

**Эндпоинт:** `GET /files/{file_id}/download-range`

### Заголовки

- `Range: bytes=start-end`: поддерживается возобновление загрузки.
- Ответ: `Content-Range: bytes start-end/total`, `Status: 206` при range.

---

# Мониторинг

## Prometheus Alerts

**Файл:** `docker/prometheus/alerts.yml`

### Правила

- **HighErrorRate**: HTTP 5xx > 5% за 5 минут (warning).
- **HighLatency**: p95 > 1s за 5 минут (warning).
- **HighQueueSize**: очередь > 100 задач (warning).
- **HighCPUUsage**: CPU > 80% (warning).
- **HighMemoryUsage**: память > 85% (warning).
- **LowDiskSpace**: диск > 90% (critical).

## Grafana

**Файлы:** `docker/grafana/dashboards/`

### Дашборды

- **task_performance.json**: задачи по типу, длительность (avg/p95), success/failure rate, активные задачи по статусу.
- **error_rates.json**: HTTP ошибки по endpoint/status, Celery failures, DB query errors, MinIO errors.
- **queue_size.json**: очередь по статусу, задачи в минуту, workers.
- **system_resources.json**: CPU, RAM, Disk I/O, Network (дополнение node_exporter).

## Структурированное логирование

**Модуль:** `app/logging_config.py`

### JSONFormatter

Поля:
- `timestamp`, `level`, `logger`, `message`, `module`, `function`, `line`.
- Дополнительно: `user_id`, `request_id`, `task_id`, `exception`.

### Настройка

```python
from app.logging_config import setup_logging

setup_logging(use_json=True)  # для продакшена

logger.info("Task started", extra={"user_id": 123, "task_id": 456})
```

Логи в формате JSON парсятся ELK/Loki и Prometheus.
