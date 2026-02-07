"""
Celery signals: обновление статуса задачи в БД при событиях воркера
"""
from celery.signals import task_failure, task_prerun, task_postrun, task_success
from datetime import datetime


def _get_db_sync():
    """Ленивый импорт для устранения circular import"""
    from app.database.connection import get_db_sync
    return get_db_sync()


def _get_task_id_from_request(request):
    """Извлечь task_id из аргументов задачи (первый аргумент для наших задач)."""
    if not request or not request.args:
        return None
    args = request.args
    if isinstance(args, (list, tuple)) and len(args) >= 1:
        return args[0]
    return None


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs):
    """Перед запуском: установить статус PROCESSING в БД."""
    request = kwargs.get("request")
    db_task_id = _get_task_id_from_request(request)
    if db_task_id is None:
        return

    # Ленивый импорт для устранения circular import
    from app.database.models.task import Task, TaskStatus

    db = _get_db_sync()
    try:
        t = db.query(Task).filter(Task.id == db_task_id).first()
        if t and t.status == TaskStatus.PENDING:
            t.status = TaskStatus.PROCESSING
            t.progress = 0.0
            db.commit()
    finally:
        db.close()


@task_postrun.connect
def task_postrun_handler(
    sender=None,
    task_id=None,
    task=None,
    retval=None,
    state=None,
    **kwargs
):
    """После завершения: обновить completed_at при успехе."""
    request = kwargs.get("request")
    db_task_id = _get_task_id_from_request(request)
    if db_task_id is None:
        return

    # Ленивый импорт для устранения circular import
    from app.database.models.task import Task

    db = _get_db_sync()
    try:
        t = db.query(Task).filter(Task.id == db_task_id).first()
        if t and state == "SUCCESS":
            t.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """При ошибке: статус FAILED и error_message."""
    request = kwargs.get("request")
    db_task_id = _get_task_id_from_request(request)
    if db_task_id is None:
        return

    # Ленивый импорт для устранения circular import
    from app.database.models.task import Task, TaskStatus

    db = _get_db_sync()
    try:
        t = db.query(Task).filter(Task.id == db_task_id).first()
        if t:
            t.status = TaskStatus.FAILED
            t.error_message = str(exception) if exception else "Unknown error"
            db.commit()
    finally:
        db.close()


@task_success.connect
def task_success_handler(sender=None, task_id=None, retval=None, **kwargs):
    """При успехе: статус COMPLETED и результат (если задача сама не обновила)."""
    request = kwargs.get("request")
    db_task_id = _get_task_id_from_request(request)
    if db_task_id is None:
        return

    # Ленивый импорт для устранения circular import
    from app.database.models.task import Task, TaskStatus

    db = _get_db_sync()
    try:
        t = db.query(Task).filter(Task.id == db_task_id).first()
        if t and t.status != TaskStatus.COMPLETED and retval and isinstance(retval, dict):
            t.status = TaskStatus.COMPLETED
            t.progress = 100.0
            t.completed_at = datetime.utcnow()
            t.result = retval
            db.commit()
    finally:
        db.close()