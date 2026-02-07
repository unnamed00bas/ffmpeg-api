"""
Prometheus metrics
"""
from fastapi import FastAPI
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

# HTTP запросы
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

# Время обработки запросов
http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# FFmpeg задачи
ffmpeg_tasks_total = Counter(
    'ffmpeg_tasks_total',
    'Total FFmpeg tasks processed',
    ['type', 'status']
)

# Время обработки FFmpeg задач
ffmpeg_task_duration_seconds = Histogram(
    'ffmpeg_task_duration_seconds',
    'FFmpeg task duration in seconds',
    ['type']
)

# Размер файлов
file_size_bytes = Histogram(
    'file_size_bytes',
    'File size in bytes',
    ['type']  # 'input' или 'output'
)

# Размер очереди задач
queue_size = Gauge(
    'queue_size',
    'Current queue size',
    ['status']  # 'pending', 'processing', 'failed'
)

# Активные workers
active_workers = Gauge(
    'active_workers',
    'Number of active workers'
)

# Использование CPU и памяти (если доступно)
cpu_usage_percent = Gauge(
    'cpu_usage_percent',
    'CPU usage percentage'
)

memory_usage_bytes = Gauge(
    'memory_usage_bytes',
    'Memory usage in bytes'
)


def setup_metrics(app: FastAPI):
    """Настройка метрик для FastAPI приложения"""

    @app.get("/metrics")
    async def metrics():
        """Endpoint для Prometheus метрик"""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )

    # Middleware для автоматического сбора метрик
    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        """Middleware для сбора метрик HTTP запросов"""
        method = request.method
        path = request.url.path

        # Игнорирование health check и metrics
        if path in ["/health", "/metrics", "/favicon.ico"]:
            return await call_next(request)

        # Замер времени
        import time
        start_time = time.time()

        # Выполнение запроса
        response = await call_next(request)

        # Вычисление времени
        duration = time.time() - start_time

        # Обновление метрик
        http_requests_total.labels(
            method=method,
            endpoint=path,
            status_code=response.status_code
        ).inc()

        http_request_duration_seconds.labels(
            method=method,
            endpoint=path
        ).observe(duration)

        return response


# Функции для обновления метрик задач
def track_task_created(task_type: str):
    """Отслеживание создания задачи"""
    ffmpeg_tasks_total.labels(type=task_type, status='pending').inc()
    queue_size.labels(status='pending').inc()


def track_task_started(task_type: str):
    """Отслеживание начала обработки задачи"""
    ffmpeg_tasks_total.labels(type=task_type, status='processing').inc()
    queue_size.labels(status='pending').dec()
    queue_size.labels(status='processing').inc()


def track_task_completed(task_type: str, duration: float):
    """Отслеживание завершения задачи"""
    ffmpeg_tasks_total.labels(type=task_type, status='completed').inc()
    queue_size.labels(status='processing').dec()
    ffmpeg_task_duration_seconds.labels(type=task_type).observe(duration)


def track_task_failed(task_type: str, duration: float):
    """Отслеживание ошибки задачи"""
    ffmpeg_tasks_total.labels(type=task_type, status='failed').inc()
    queue_size.labels(status='processing').dec()
    ffmpeg_task_duration_seconds.labels(type=task_type).observe(duration)


def track_file_size(file_type: str, size: int):
    """Отслеживание размера файла"""
    file_size_bytes.labels(type=file_type).observe(size)
