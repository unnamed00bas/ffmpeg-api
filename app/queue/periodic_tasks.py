"""
Celery periodic tasks (Beat): очистка старых файлов, temp-объектов MinIO, старых задач.
"""
import asyncio
from datetime import datetime, timedelta

from app.queue.celery_app import celery_app


async def _async_cleanup_old_files(retention_days: int) -> int:
    """Удаление файлов старее retention_days из БД и MinIO."""
    from app.database.connection import async_session_maker
    from app.database.repositories.file_repository import FileRepository
    from app.storage.minio_client import MinIOClient

    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    storage = MinIOClient()
    deleted = 0
    async with async_session_maker() as session:
        repo = FileRepository(session)
        old_files = await repo.get_files_older_than(cutoff)
        for file_record in old_files:
            try:
                await storage.delete_file(file_record.storage_path)
            except Exception:
                pass
            await repo.mark_as_deleted(file_record.id)
            deleted += 1
        await session.commit()
    return deleted


async def _async_cleanup_temp_files() -> int:
    """Удаление временных объектов в MinIO (temp/chunks/ и т.д.) старше 24 часов."""
    from app.storage.minio_client import MinIOClient

    storage = MinIOClient()
    prefix = "temp/"
    objects = await storage.list_objects_async(prefix)
    cutoff = datetime.utcnow() - timedelta(hours=24)
    deleted = 0
    for object_name in objects:
        try:
            info = await storage.get_file_info(object_name)
            last_modified = info.get("last_modified")
            if last_modified:
                lm = last_modified.replace(tzinfo=None) if getattr(last_modified, "tzinfo", None) else last_modified
                if lm < cutoff:
                    await storage.delete_file(object_name)
                    deleted += 1
        except Exception:
            pass
    return deleted


async def _async_cleanup_old_tasks(days: int = 30) -> int:
    """Удаление записей задач старше days дней."""
    from app.database.connection import async_session_maker
    from app.database.repositories.task_repository import TaskRepository

    cutoff = datetime.utcnow() - timedelta(days=days)
    async with async_session_maker() as session:
        repo = TaskRepository(session)
        count = await repo.delete_tasks_older_than(cutoff)
        await session.commit()
        return count


@celery_app.task(name="app.queue.periodic_tasks.cleanup_old_files")
def cleanup_old_files(retention_days: int | None = None) -> str:
    """
    Периодическая очистка старых файлов (по retention): БД + MinIO.
    retention_days: из settings.STORAGE_RETENTION_DAYS если не передан.
    """
    try:
        from app.config import get_settings
        settings = get_settings()
        days = retention_days if retention_days is not None else settings.STORAGE_RETENTION_DAYS
        deleted = asyncio.run(_async_cleanup_old_files(days))
        return f"Deleted {deleted} old files"
    except Exception as e:
        return f"Error: {e}"


@celery_app.task(name="app.queue.periodic_tasks.cleanup_temp_files")
def cleanup_temp_files() -> str:
    """Периодическая очистка временных объектов в MinIO (temp/)."""
    try:
        deleted = asyncio.run(_async_cleanup_temp_files())
        return f"Deleted {deleted} temp files"
    except Exception as e:
        return f"Error: {e}"


@celery_app.task(name="app.queue.periodic_tasks.cleanup_old_tasks")
def cleanup_old_tasks(task_retention_days: int = 30) -> str:
    """Периодическая очистка старых записей задач."""
    try:
        deleted = asyncio.run(_async_cleanup_old_tasks(task_retention_days))
        return f"Deleted {deleted} old tasks"
    except Exception as e:
        return f"Error: {e}"
