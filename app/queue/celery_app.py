"""
Celery application configuration
"""
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ffmpeg_api",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.queue.tasks",
        "app.queue.periodic_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

from app.queue.beat_schedule import beat_schedule
import app.queue.signals  # noqa: F401 - register Celery signal handlers

celery_app.conf.beat_schedule = beat_schedule
