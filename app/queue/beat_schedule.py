"""
Celery Beat schedule for periodic tasks
"""
from celery.schedules import crontab

beat_schedule = {
    "cleanup-old-files-every-6-hours": {
        "task": "app.queue.periodic_tasks.cleanup_old_files",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "cleanup-temp-files-every-hour": {
        "task": "app.queue.periodic_tasks.cleanup_temp_files",
        "schedule": crontab(minute=0),
    },
    "cleanup-old-tasks-daily": {
        "task": "app.queue.periodic_tasks.cleanup_old_tasks",
        "schedule": crontab(minute=0, hour=2),
    },
}
