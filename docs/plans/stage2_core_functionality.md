# Этап 2: Основной функционал (Недели 3-5)

## Обзор этапа

Этап реализует основной функционал MVP: очереди задач, загрузку файлов, обработку видео через FFmpeg (объединение видео), и управление задачами. К концу этапа сервис будет способен принимать и обрабатывать задачи на объединение видео.

---

## Подзадача 2.1: Очередь задач (Celery)

### Задачи реализации

**Настройка Celery app в [app/queue/celery_app.py](app/queue/celery_app.py):**

```python
celery_app = Celery(
    "ffmpeg_api",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.queue.tasks",
        "app.queue.periodic_tasks",
    ]
)

# Настройки
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
```

**Настройка Celery Beat в [app/queue/beat_schedule.py](app/queue/beat_schedule.py):**

```python
from celery.schedules import crontab

beat_schedule = {
    "cleanup-old-files-every-hour": {
        "task": "app.queue.periodic_tasks.cleanup_old_files",
        "schedule": crontab(minute=0),
    },
    "cleanup-temp-files-every-30min": {
        "task": "app.queue.periodic_tasks.cleanup_temp_files",
        "schedule": crontab(minute="*/30"),
    },
}
```

**Task Pydantic schemas в [app/schemas/task.py](app/schemas/task.py):**

```python
class TaskType(str, Enum):
    JOIN = "join"
    AUDIO_OVERLAY = "audio_overlay"
    TEXT_OVERLAY = "text_overlay"
    SUBTITLES = "subtitles"
    VIDEO_OVERLAY = "video_overlay"
    COMBINED = "combined"

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskCreate(BaseModel):
    type: TaskType
    config: Dict[str, Any]
    priority: int = Field(default=5, ge=1, le=10)

class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    progress: Optional[float] = Field(None, ge=0, le=100)
    error_message: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    user_id: int
    type: TaskType
    status: TaskStatus
    input_files: List[int]
    output_files: List[int]
    config: Dict[str, Any]
    error_message: Optional[str]
    progress: float
    result: Optional[Dict[str, Any]]
    retry_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

class TaskListResponse(BaseModel):
    tasks: List[TaskResponse]
    total: int
    page: int
    page_size: int
```

**Task service в [app/services/task_service.py](app/services/task_service.py):**

```python
class TaskService:
    async def create_task(
        user_id: int,
        task_type: TaskType,
        config: Dict[str, Any],
        priority: int = 5
    ) -> Task
    
    async def get_task(task_id: int, user_id: int) -> Optional[Task]
    
    async def get_tasks(
        user_id: int,
        status: Optional[TaskStatus] = None,
        task_type: Optional[TaskType] = None,
        offset: int = 0,
        limit: int = 20
    ) -> TaskListResponse
    
    async def cancel_task(task_id: int, user_id: int) -> bool
    
    async def retry_task(task_id: int, user_id: int) -> Task
    
    async def update_status(
        task_id: int,
        status: TaskStatus,
        error_message: Optional[str] = None
    ) -> Task
    
    async def update_progress(task_id: int, progress: float) -> Task
    
    async def update_result(task_id: int, result: Dict[str, Any]) -> Task
```

**Приоритеты задач:**
- 10: urgent (высочайший)
- 8-9: high
- 5-7: normal (default)
- 3-4: low
- 1-2: background

**Retry логика:**
```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # seconds
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
    retry_backoff_max=300,  # 5 minutes max
    retry_jitter=True,
)
def my_processing_task(self, task_id: int, config: dict):
    # Task implementation
    pass
```

### Тестирование подзадачи 2.1

**Unit тесты TaskService:**
- create_task() создает запись в БД с корректными полями
- create_task() присваивает приоритет
- get_task() возвращает задачу пользователя
- get_task() возвращает None для несуществующей задачи
- get_task() возвращает None для задачи другого пользователя
- get_tasks() возвращает пагинированный список
- get_tasks() фильтрует по статусу
- get_tasks() фильтрует по типу
- get_tasks() сортирует по created_at DESC
- cancel_task() отменяет PENDING задачу
- cancel_task() отменяет PROCESSING задачу
- cancel_task() не отменяет COMPLETED задачу
- retry_task() увеличивает retry_count
- retry_task() сбрасывает статус в PENDING
- retry_task() создает новую Celery задачу
- update_status() обновляет статус и updated_at
- update_status() устанавливает completed_at при статусе COMPLETED
- update_progress() обновляет прогресс
- update_result() сохраняет результат в JSON

**Unit тесты retry логики:**
- Task retry'ится 3 раза при TemporaryError
- Retry delay увеличивается с exponential backoff
- Max retry delay не превышает 300 секунд
- Task не retry'ится при PermanentError
- Jitter добавляет случайность к delay

**Интеграционные тесты Celery:**

*Базовые функции:*
- Задачи успешно добавляются в очередь Redis
- Celery worker получает задачи из очереди
- Результаты сохраняются в Redis backend
- Task ID корректно связывает Celery задачу с БД

*Приоритеты:*
- High priority задачи обрабатываются раньше normal
- Urgent задачи обрабатываются раньше high
- Задачи с одинаковым приоритетом обрабатываются в порядке FIFO

*Retry логика:*
- Failed задачи retry'ятся автоматически
- Retry_count увеличивается корректно
- Max retries не превышается
- Задача помечается как FAILED после max retries

*Celery signals:*
- task_prerun сигнал вызывается перед выполнением
- task_postrun сигнал вызывается после выполнения
- task_failure сигнал вызывается при ошибке
- task_success сигнал вызывается при успехе

**Тесты Flower:**
- Flower доступен на http://localhost:5555
- Flower показывает все задачи
- Flower показывает worker статус
- Flower показывает queue size
- Flower позволяет отменять задачи

**Load тесты:**
- Обработка 10 задач параллельно работает без ошибок
- Обработка 50 задач параллельно работает без ошибок
- Обработка 100 задач параллельно работает без ошибок
- Очередь не блокируется при нагрузке
- Worker не падает при большом количестве задач

---

## Подзадача 2.2: Загрузка файлов

### Задачи реализации

**MinIO клиент в [app/storage/minio_client.py](app/storage/minio_client.py):**

```python
class MinIOClient:
    def __init__(self):
        self.client = Minio(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=False,  # HTTP в Docker
        )
        self.bucket_name = settings.MINIO_BUCKET_NAME
        self._ensure_bucket_exists()
    
    async def upload_file(
        self,
        file_path: str,
        object_name: str,
        content_type: str
    ) -> str:
        """Загрузка файла и возврат object_name"""
    
    async def download_file(
        self,
        object_name: str,
        file_path: str
    ) -> None:
        """Скачивание файла"""
    
    async def delete_file(self, object_name: str) -> None:
        """Удаление файла"""
    
    async def get_file_url(
        self,
        object_name: str,
        expires: timedelta = timedelta(hours=1)
    ) -> str:
        """Генерация presigned URL"""
    
    async def file_exists(self, object_name: str) -> bool:
        """Проверка существования файла"""
    
    async def get_file_info(self, object_name: str) -> Dict[str, Any]:
        """Получение информации о файле"""
```

**File storage service в [app/services/file_service.py](app/services/file_service.py):**

```python
class FileService:
    async def upload_from_request(
        self,
        user_id: int,
        filename: str,
        content: bytes,
        content_type: str
    ) -> File
    
    async def upload_from_url(
        self,
        user_id: int,
        url: str
    ) -> File:
        """Загрузка файла по URL"""
    
    async def validate_file(
        self,
        filename: str,
        content_type: str,
        size: int
    ) -> bool:
        """Валидация файла"""
    
    async def get_file_info(self, file_id: int, user_id: int) -> Optional[File]
    
    async def get_user_files(
        self,
        user_id: int,
        offset: int = 0,
        limit: int = 20
    ) -> List[File]
    
    async def delete_file(self, file_id: int, user_id: int) -> bool
    
    async def download_file(
        self,
        file_id: int,
        user_id: int
    ) -> bytes:
        """Получение содержимого файла"""
```

**File Pydantic schemas в [app/schemas/file.py](app/schemas/file.py):**

```python
class FileMetadata(BaseModel):
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    bitrate: Optional[int] = None

class FileUploadResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    size: int
    content_type: str
    metadata: Optional[FileMetadata]
    created_at: datetime
    download_url: str

class FileInfo(BaseModel):
    id: int
    original_filename: str
    size: int
    content_type: str
    metadata: Optional[FileMetadata]
    created_at: datetime
```

**Валидация файлов:**

```python
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "avi", "mov", "mkv", "wmv"}
ALLOWED_AUDIO_EXTENSIONS = {"mp3", "aac", "wav", "flac", "ogg"}
ALLOWED_SUBTITLE_EXTENSIONS = {"srt", "vtt", "ass", "ssa"}

ALLOWED_CONTENT_TYPES = {
    "video": {"video/mp4", "video/avi", "video/quicktime", "video/x-matroska", "video/x-ms-wmv"},
    "audio": {"audio/mpeg", "audio/aac", "audio/wav", "audio/flac", "audio/ogg"},
    "subtitle": {"text/plain", "text/vtt", "text/x-ssa"},
}
```

**Files endpoints в [app/api/v1/files.py](app/api/v1/files.py):**

- POST /api/v1/files/upload:
  - Headers: Authorization: Bearer {token}
  - Body: multipart/form-data с файлом
  - Response: FileUploadResponse
  - Валидация: размер, тип, расширение

- POST /api/v1/files/upload-url:
  - Headers: Authorization: Bearer {token}
  - Body: {url: str}
  - Response: FileUploadResponse
  - Download по URL с timeout

- GET /api/v1/files/{file_id}:
  - Headers: Authorization: Bearer {token}
  - Response: FileInfo
  - Проверка прав доступа

- GET /api/v1/files/{file_id}/download:
  - Headers: Authorization: Bearer {token}
  - Response: file content (stream)
  - Streaming для больших файлов

- DELETE /api/v1/files/{file_id}:
  - Headers: Authorization: Bearer {token}
  - Response: 204 No Content
  - Удаление из MinIO и БД

- GET /api/v1/files:
  - Headers: Authorization: Bearer {token}
  - Query: ?offset=0&limit=20
  - Response: {files: [], total: int, page: int, page_size: int}

### Тестирование подзадачи 2.2

**Unit тесты валидации файлов:**
- validate_file() возвращает True для разрешенных видео расширений
- validate_file() возвращает False для запрещенных расширений
- validate_file() возвращает True для разрешенных аудио расширений
- validate_file() проверяет размер файла (MAX_UPLOAD_SIZE)
- validate_file() проверяет content-type
- validate_file() возвращает False для слишком больших файлов
- validate_file() возвращает False для некорректного content-type

**Unit тесты FileService:**
- upload_from_request() загружает файл в MinIO
- upload_from_request() создает запись в БД
- upload_from_request() возвращает File объект
- upload_from_url() скачивает файл по URL
- upload_from_url() обрабатывает ошибки сети
- upload_from_url() имеет timeout
- get_file_info() возвращает файл пользователя
- get_file_info() возвращает None для чужого файла
- get_user_files() возвращает пагинированный список
- delete_file() удаляет файл из MinIO
- delete_file() помечает файл как удаленный в БД
- delete_file() не удаляет чужой файл
- download_file() возвращает содержимое файла

**Интеграционные тесты MinIO:**

*Базовые операции:*
- upload_file() успешно загружает файл
- upload_file() возвращает корректный object_name
- download_file() успешно скачивает файл
- download_file() сохраняет файл в указанную директорию
- delete_file() успешно удаляет файл
- file_exists() возвращает True для существующего файла
- file_exists() возвращает False для несуществующего файла
- get_file_info() возвращает корректные метаданные

*Presigned URLs:*
- get_file_url() генерирует валидную presigned URL
- Presigned URL работает в браузере
- Presigned URL истекает через указанное время
- Presigned URL работает для больших файлов

**API endpoint тесты:**

*POST /api/v1/files/upload:*
- Успешная загрузка возвращает 201 и FileUploadResponse
- Загрузка без авторизации возвращает 401
- Загрузка файла > MAX_UPLOAD_SIZE возвращает 413
- Загрузка файла с запрещенным расширением возвращает 422
- Загрузка файла с некорректным content-type возвращает 422
- Файл сохраняется в MinIO
- Запись создается в БД
- download_url возвращает working URL

*POST /api/v1/files/upload-url:*
- Успешная загрузка по URL возвращает 201
- Загрузка по невалидному URL возвращает 400
- Загрузка по URL с timeout возвращает 504
- Загрузка по URL с недоступным сервером возвращает 502
- Файл скачивается корректно

*GET /api/v1/files/{file_id}:*
- Успешный запрос возвращает 200 и FileInfo
- Запрос без авторизации возвращает 401
- Запрос чужого файла возвращает 403
- Запрос несуществующего файла возвращает 404

*GET /api/v1/files/{file_id}/download:*
- Успешный запрос возвращает 200 и файл
- Запрос стримит большие файлы (chunked encoding)
- Content-Type корректен
- Content-Length корректен
- Request без авторизации возвращает 401
- Request чужого файла возвращает 403

*DELETE /api/v1/files/{file_id}:*
- Успешное удаление возвращает 204
- Удаление без авторизации возвращает 401
- Удаление чужого файла возвращает 403
- Удаление несуществующего файла возвращает 404
- Файл удален из MinIO
- Запись помечена как удаленная в БД

*GET /api/v1/files:*
- Успешный запрос возвращает список файлов
- Пагинация работает корректно
- Сортировка по created_at DESC
- Только файлы пользователя
- total указывает общее количество

**Performance тесты:**
- Загрузка 1MB файла < 2 сек
- Загрузка 100MB файла < 30 сек
- Загрузка 1GB файла < 5 мин
- Скачивание 1GB файла использует стриминг (RAM не растет)
- MinIO operations < 100ms

---

## Подзадача 2.3: FFmpeg базовый процессор

### Задачи реализации

**Base processor класс в [app/processors/base_processor.py](app/processors/base_processor.py):**

```python
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any

class BaseProcessor(ABC):
    def __init__(
        self,
        task_id: int,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[float], None]] = None
    ):
        self.task_id = task_id
        self.config = config
        self.progress_callback = progress_callback
        self.temp_files: List[str] = []
    
    @abstractmethod
    async def validate_input(self) -> None:
        """Валидация входных данных"""
        pass
    
    @abstractmethod
    async def process(self) -> Dict[str, Any]:
        """Основная обработка"""
        pass
    
    async def run(self) -> Dict[str, Any]:
        """Запуск процессора"""
        await self.validate_input()
        result = await self.process()
        await self.cleanup()
        return result
    
    async def cleanup(self) -> None:
        """Очистка временных файлов"""
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def update_progress(self, progress: float) -> None:
        """Обновление прогресса"""
        if self.progress_callback:
            self.progress_callback(progress)
    
    def add_temp_file(self, file_path: str) -> None:
        """Добавление временного файла"""
        self.temp_files.append(file_path)
```

**FFmpeg commands wrapper в [app/ffmpeg/commands.py](app/ffmpeg/commands.py):**

```python
import asyncio
import json
from typing import Dict, Any

class FFmpegCommand:
    @staticmethod
    async def run_command(
        command: List[str],
        timeout: int = 3600,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> str:
        """Запуск FFmpeg команды"""
    
    @staticmethod
    async def get_video_info(file_path: str) -> Dict[str, Any]:
        """Получение информации о видео"""
    
    @staticmethod
    async def get_audio_info(file_path: str) -> Dict[str, Any]:
        """Получение информации об аудио"""
    
    @staticmethod
    async def validate_file(file_path: str) -> bool:
        """Валидация файла FFmpeg"""
    
    @staticmethod
    def parse_ffmpeg_progress(output: str) -> float:
        """Парсинг прогресса из stderr"""
```

**FFmpeg утилиты в [app/ffmpeg/utils.py](app/ffmpeg/utils.py):**

```python
def format_duration(seconds: float) -> str:
    """Форматирование длительности HH:MM:SS"""
    
def parse_duration(duration_str: str) -> float:
    """Парсинг длительности из строки"""
    
def parse_ffmpeg_output(stderr: str) -> Dict[str, Any]:
    """Парсинг вывода FFmpeg"""
    
def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """Получение метаданных файла"""
```

**FFmpeg exceptions в [app/ffmpeg/exceptions.py](app/ffmpeg/exceptions.py):**

```python
class FFmpegError(Exception):
    """Базовое исключение FFmpeg"""
    pass

class FFmpegValidationError(FFmpegError):
    """Ошибка валидации"""
    pass

class FFmpegProcessingError(FFmpegError):
    """Ошибка обработки"""
    pass

class FFmpegTimeoutError(FFmpegError):
    """Таймаут выполнения"""
    pass
```

**Temporary file management в [app/utils/temp_files.py](app/utils/temp_files.py):**

```python
import tempfile
import os

def create_temp_file(
    suffix: str = "",
    prefix: str = "ffmpeg_",
    directory: Optional[str] = None
) -> str:
    """Создание временного файла"""
    
def create_temp_dir(
    prefix: str = "ffmpeg_",
    suffix: str = ""
) -> str:
    """Создание временной директории"""
    
def cleanup_temp_files(temp_files: List[str]) -> None:
    """Очистка временных файлов"""
    
def cleanup_old_files(
    directory: str,
    max_age_hours: int = 24
) -> int:
    """Очистка старых временных файлов"""
```

### Тестирование подзадачи 2.3

**Unit тесты BaseProcessor:**
- validate_input() вызывается перед process()
- validate_input() выбрасывает исключение при неверных данных
- process() вызывается после validate_input()
- cleanup() вызывается после process()
- cleanup() вызывается даже при ошибке в process()
- cleanup() удаляет все временные файлы
- update_progress() вызывает callback
- add_temp_file() добавляет файл в список

**Unit тесты FFmpeg commands:**

*run_command:*
- run_command() выполняет корректную команду
- run_command() возвращает stdout
- run_command() выбрасывает исключение при неверном коде возврата
- run_command() выбрасывает FFmpegTimeoutError при timeout
- run_command() вызывает progress_callback для FFmpeg прогресса
- run_command() использует asyncio subprocess

*get_video_info:*
- get_video_info() возвращает корректную информацию
- get_video_info() возвращает duration, width, height, codec
- get_video_info() выбрасывает исключение для несуществующего файла

*get_audio_info:*
- get_audio_info() возвращает корректную информацию
- get_audio_info() возвращает duration, codec, bitrate
- get_audio_info() выбрасывает исключение для несуществующего файла

*validate_file:*
- validate_file() возвращает True для валидного видео
- validate_file() возвращает True для валидного аудио
- validate_file() возвращает False для поврежденного файла

*parse_ffmpeg_progress:*
- parse_ffmpeg_progress() парсит progress из stderr
- parse_ffmpeg_progress() возвращает 0.0-100.0
- parse_ffmpeg_progress() возвращает None при отсутствии прогресса

**Unit тесты FFmpeg utils:**
- format_duration() форматирует секунды в HH:MM:SS
- parse_duration() парсит HH:MM:SS в секунды
- parse_ffmpeg_output() извлекает метаданные
- get_file_metadata() возвращает словарь с метаданными

**Unit тесты временных файлов:**
- create_temp_file() создает файл
- create_temp_file() использует указанный suffix/prefix
- create_temp_dir() создает директорию
- create_temp_dir() использует указанный prefix/suffix
- cleanup_temp_files() удаляет все файлы
- cleanup_temp_files() игнорирует несуществующие файлы
- cleanup_old_files() удаляет файлы старше max_age_hours
- cleanup_old_files() возвращает количество удаленных файлов

**Интеграционные тесты FFmpeg:**

*Базовые команды:*
- FFmpeg установлен и доступен
- FFprobe установлен и доступен
- Простая команда выполняется успешно
- Команда с ошибкой выбрасывает исключение

*Обработка ошибок:*
- FFmpeg ошибки детерминированы
- stderr парсится корректно
- Exception содержит полезное сообщение

*Progress tracking:*
- Progress callback вызывается для длинных операций
- Progress монотонно возрастает
- Progress достигает 100.0 при завершении

**Тесты cleanup:**
- Временные файлы удаляются при успехе
- Временные файлы удаляются при ошибке
- Нет утечки временных файлов
- Временные директории очищаются

---

## Подзадача 2.4: Объединение видео (Join)

### Задачи реализации

**VideoJoiner processor в [app/processors/video_joiner.py](app/processors/video_joiner.py):**

```python
class VideoJoiner(BaseProcessor):
    async def validate_input(self) -> None:
        """Валидация входных видео"""
        # Проверка количества файлов (минимум 2)
        # Проверка совпадения разрешения
        # Проверка совпадения FPS
        # Проверка совпадения видео кодека
        # Проверка длительности
    
    async def _create_concat_list(self, video_files: List[str]) -> str:
        """Создание concat списка"""
        # Генерация файла со списком путей к видео
    
    async def process(self) -> Dict[str, Any]:
        """Объединение видео через FFmpeg concat demuxer"""
        # Создание concat списка
        # Запуск FFmpeg команды
        # Проверка результата
        # Возврат выходного файла
    
    def _generate_ffmpeg_command(
        self,
        concat_list: str,
        output_file: str
    ) -> List[str]:
        """Генерация FFmpeg команды для join"""
        return [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-c", "copy",  # Без перекодирования (быстрее)
            output_file
        ]
```

**Celery task в [app/queue/tasks.py](app/queue/tasks.py):**

```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(TemporaryError,),
    retry_backoff=True,
)
def join_video_task(self, task_id: int, config: dict) -> dict:
    """Celery задача для объединения видео"""
    try:
        # Обновление статуса в PROCESSING
        # Получение файлов из MinIO
        # Создание VideoJoiner
        # Запуск обработки
        # Сохранение результата в MinIO
        # Обновление статуса в COMPLETED
        # Возврат результата
    except Exception as exc:
        # Обновление статуса в FAILED
        # Повтор задачи (если возможно)
        raise
```

**Task endpoint в [app/api/v1/tasks.py](app/api/v1/tasks.py):**

- POST /api/v1/tasks/join:
  - Headers: Authorization: Bearer {token}
  - Body: {file_ids: [int], output_filename: str}
  - Response: TaskResponse
  - Создает задачу в БД
  - Добавляет задачу в Celery

### Тестирование подзадачи 2.4

**Unit тесты VideoJoiner:**

*Валидация:*
- validate_input() проходит для 2+ файлов
- validate_input() выбрасывает исключение для 1 файла
- validate_input() проверяет совпадение разрешения
- validate_input() проверяет совпадение FPS
- validate_input() проверяет совпадение кодека

*Создание concat списка:*
- _create_concat_list() создает корректный файл
- _create_concat_list() использует правильный формат
- _create_concat_list() обрабатывает специальные символы в путях

*Генерация команды:*
- _generate_ffmpeg_command() генерирует корректную команду
- _generate_ffmpeg_command() использует -f concat -safe 0
- _generate_ffmpeg_command() использует -c copy

**Unit тесты Celery task:**
- join_video_task() создает запись в БД
- join_video_task() получает файлы из MinIO
- join_video_task() вызывает VideoJoiner
- join_video_task() обновляет статус в PROCESSING
- join_video_task() обновляет статус в COMPLETED при успехе
- join_video_task() обновляет статус в FAILED при ошибке
- join_video_task() сохраняет результат в MinIO
- join_video_task() retry'ится при TemporaryError
- join_video_task() не retry'ится при PermanentError

**Интеграционные тесты:**

*Базовые сценарии:*
- Объединение 2 видео работает
- Объединение 5 видео работает
- Объединение 10 видео работает
- Выходной файл имеет корректную длительность
- Выходной файл имеет корректное разрешение

*Несовместимые видео:*
- Несовпадение разрешения выбрасывает исключение
- Несовпадение FPS выбрасывает исключение
- Несовпадение кодека выбрасывает исключение

*Разные качества:*
- Видео одинакового качества объединяются успешно
- Видео разного качества (но совпадающих параметров) объединяются

**API endpoint тесты:**

*POST /api/v1/tasks/join:*
- Успешный запрос возвращает 201 и TaskResponse
- Задача создается в БД
- Задача добавляется в Celery
- Задача имеет статус PENDING
- Запрос без авторизации возвращает 401
- Запрос с 1 файлом возвращает 422
- Запрос с несуществующими файлами возвращает 404
- Запрос с несовместимыми видео приводит к FAILED статусу

**Regression тесты:**
- Разные типы видео (mp4, avi, mov)
- Разные разрешения (720p, 1080p, 4K)
- Разные FPS (24, 25, 30, 60)
- Разные кодеки (h264, h265)

---

## Подзадача 2.5: Task management

### Задачи реализации

**Реализация TaskService методов:**

```python
class TaskService:
    # ... (методы из подзадачи 2.1)
    
    async def create_task(
        self,
        user_id: int,
        task_type: TaskType,
        config: Dict[str, Any],
        file_ids: List[int],
        priority: int = 5
    ) -> Task:
        """Создание задачи с валидацией"""
        # Проверка прав доступа к файлам
        # Валидация конфигурации
        # Создание задачи в БД
        # Создание Celery задачи
        # Возврат задачи
    
    async def get_task_with_result(
        self,
        task_id: int,
        user_id: int
    ) -> Optional[Task]:
        """Получение задачи с результатом"""
        # Получение задачи
        # Получение URL выходных файлов
        # Возврат задачи
    
    async def get_tasks_with_filters(
        self,
        user_id: int,
        filters: Dict[str, Any],
        offset: int = 0,
        limit: int = 20
    ) -> TaskListResponse:
        """Получение задач с фильтрами"""
        # Применение фильтров
        # Пагинация
        # Сортировка
        # Возврат списка
```

**Celery signals в [app/queue/signals.py](app/queue/signals.py):**

```python
from celery.signals import task_prerun, task_postrun, task_failure, task_success

@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Перед запуском задачи"""
    # Обновление статуса в PROCESSING

@task_postrun.connect
def task_postrun_handler(
    sender=None,
    task_id=None,
    task=None,
    retval=None,
    state=None,
    **kwargs
):
    """После завершения задачи"""
    # Обновление времени завершения

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """При ошибке задачи"""
    # Обновление статуса в FAILED
    # Сохранение error_message

@task_success.connect
def task_success_handler(sender=None, task_id=None, retval=None, **kwargs):
    """При успешном завершении"""
    # Обновление статуса в COMPLETED
    # Сохранение результата
```

**Task endpoints в [app/api/v1/tasks.py](app/api/v1/tasks.py):**

- POST /api/v1/tasks:
  - Headers: Authorization: Bearer {token}
  - Body: {type, config, file_ids, priority}
  - Response: TaskResponse

- GET /api/v1/tasks:
  - Headers: Authorization: Bearer {token}
  - Query: ?status=processing&type=join&offset=0&limit=20
  - Response: TaskListResponse

- GET /api/v1/tasks/{task_id}:
  - Headers: Authorization: Bearer {token}
  - Response: TaskResponse

- POST /api/v1/tasks/{task_id}/cancel:
  - Headers: Authorization: Bearer {token}
  - Response: TaskResponse

- POST /api/v1/tasks/{task_id}/retry:
  - Headers: Authorization: Bearer {token}
  - Response: TaskResponse

### Тестирование подзадачи 2.5

**Unit тесты TaskService:**

*create_task:*
- create_task() создает задачу с корректными полями
- create_task() проверяет права доступа к файлам
- create_task() валидирует конфигурацию
- create_task() создает Celery задачу
- create_task() выбрасывает исключение для чужих файлов

*get_task_with_result:*
- get_task_with_result() возвращает задачу с результатом
- get_task_with_result() генерирует presigned URL для выходных файлов
- get_task_with_result() возвращает None для несуществующей задачи

*get_tasks_with_filters:*
- get_tasks_with_filters() применяет фильтр по статусу
- get_tasks_with_filters() применяет фильтр по типу
- get_tasks_with_filters() применяет фильтр по дате
- get_tasks_with_filters() поддерживает несколько фильтров
- get_tasks_with_filters() возвращает пагинированный список
- get_tasks_with_filters() сортирует по created_at DESC

**Интеграционные тесты:**

*Task lifecycle:*
- Задача создается со статусом PENDING
- Задача переходит в PROCESSING перед выполнением
- Задача переходит в COMPLETED при успехе
- Задача переходит в FAILED при ошибке
- Задача обновляет прогресс во время выполнения

*Celery signals:*
- task_prerun обновляет статус в PROCESSING
- task_postrun обновляет completed_at
- task_failure обновляет статус в FAILED
- task_success обновляет статус в COMPLETED
- task_failure сохраняет error_message
- task_success сохраняет результат

**API endpoint тесты:**

*POST /api/v1/tasks:*
- Успешный запрос возвращает 201 и TaskResponse
- Задача создается для корректного типа
- Задача не создается для некорректного типа
- Запрос без авторизации возвращает 401

*GET /api/v1/tasks:*
- Успешный запрос возвращает список задач
- Пагинация работает корректно
- Фильтр по статусу работает
- Фильтр по типу работает
- Сортировка по created_at DESC
- Только задачи пользователя

*GET /api/v1/tasks/{task_id}:*
- Успешный запрос возвращает TaskResponse
- Запрос без авторизации возвращает 401
- Запрос чужой задачи возвращает 403
- Запрос несуществующей задачи возвращает 404

*POST /api/v1/tasks/{task_id}/cancel:*
- Успешная отмена PENDING задачи возвращает 200
- Успешная отмена PROCESSING задачи возвращает 200
- Отмена COMPLETED задачи возвращает 400
- Отмена FAILED задачи возвращает 400
- Запрос без авторизации возвращает 401
- Запрос чужой задачи возвращает 403

*POST /api/v1/tasks/{task_id}/retry:*
- Успешный retry FAILED задачи возвращает 200
- Retry увеличивает retry_count
- Retry сбрасывает статус в PENDING
- Retry создает новую Celery задачу
- Retry COMPLETED задачи возвращает 400
- Retry PENDING задачи возвращает 400
- Запрос без авторизации возвращает 401
- Запрос чужой задачи возвращает 403

**Тесты прав доступа:**
- Пользователь видит только свои задачи
- Пользователь не может отменить чужую задачу
- Пользователь не может retry'ить чужую задачу
- Пользователь не может видеть детали чужой задачи

---

## Критерии завершения Этапа 2

**Функциональные требования:**
- Celery очереди работают и обрабатывают задачи
- Worker обрабатывает задачи параллельно
- Flower мониторинг работает
- Загрузка файлов через multipart работает
- Загрузка файлов по URL работает
- Валидация файлов работает
- FFmpeg базовый процессор работает
- Объединение видео работает
- Task management endpoints работают
- Все Celery signals работают

**Требования к тестированию:**
- Все unit тесты проходят
- Все интеграционные тесты проходят
- Load тесты: 100 concurrent requests
- Coverage > 75% для кода этапа 2

**Документация:**
- Processors документированы (docstrings)
- Services документированы (docstrings)
- API endpoints документированы в OpenAPI
- Примеры запросов/ответов добавлены

**Производительность:**
- Загрузка файла < 30 сек для 100MB
- Обработка видео (join) < 2x реального времени
- API response time < 200ms
- Worker не падает при нагрузке
