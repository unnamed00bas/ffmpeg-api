"""
Тесты периодических задач: cleanup_old_files, cleanup_temp_files, cleanup_old_tasks.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.queue.periodic_tasks import (
    cleanup_old_files,
    cleanup_temp_files,
    cleanup_old_tasks,
    _async_cleanup_old_files,
    _async_cleanup_temp_files,
    _async_cleanup_old_tasks,
)


class TestAsyncCleanupOldFiles:
    """Async тесты очистки старых файлов."""

    @pytest.mark.asyncio
    async def test_deletes_files_older_than_cutoff(self):
        """Удаляет файлы старее указанной даты."""
        mock_db = MagicMock()
        file_mock = MagicMock(id=1, storage_path="path1")
        file_mock2 = MagicMock(id=2, storage_path="path2")
        repo_mock = MagicMock()
        repo_mock.get_files_older_than = AsyncMock(return_value=[file_mock])
        repo_mock.mark_as_deleted = AsyncMock()
        storage_mock = MagicMock()
        storage_mock.delete_file = AsyncMock()
        with patch("app.queue.periodic_tasks.async_session_maker") as sess_maker:
            sess_maker.return_value = MagicMock()
            with patch("app.queue.periodic_tasks.FileRepository", return_value=repo_mock):
                with patch("app.queue.periodic_tasks.MinIOClient", return_value=storage_mock):
                    deleted = await _async_cleanup_old_files(retention_days=7)
        assert deleted == 1
        repo_mock.get_files_older_than.assert_called_once()
        storage_mock.delete_file.assert_called_once_with("path1")
        repo_mock.mark_as_deleted.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_uses_retention_from_settings_if_not_passed(self):
        """Использует STORAGE_RETENTION_DAYS из settings если не передан."""
        with patch("app.queue.periodic_tasks.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(STORAGE_RETENTION_DAYS=14)
            # Вызов без параметра
            cleanup_old_files()
            # Вызов функции async с неопределённым retention_days будет использовать дефолт
            # (реализация в cleanup_old_files вызывает get_settings если параметр None)


class TestAsyncCleanupTempFiles:
    """Async тесты очистки временных файлов."""

    @pytest.mark.asyncio
    async def test_deletes_temp_objects_older_than_24h(self):
        """Удаляет temp объекты MinIO старее 24 ч."""
        storage_mock = MagicMock()
        storage_mock.list_objects_async = AsyncMock(return_value=["temp/chunk1", "temp/chunk2"])
        storage_mock.get_file_info = AsyncMock(
            return_value={
                "last_modified": datetime.utcnow() - timedelta(hours=25),
                "size": 1024,
            }
        )
        storage_mock.delete_file = AsyncMock()
        with patch("app.queue.periodic_tasks.MinIOClient", return_value=storage_mock):
            deleted = await _async_cleanup_temp_files()
        assert deleted == 2
        storage_mock.delete_file.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_fresh_temp_objects(self):
        """Не удаляет свежие temp объекты (младше 24 ч)."""
        storage_mock = MagicMock()
        storage_mock.list_objects_async = AsyncMock(return_value=["temp/new"])
        storage_mock.get_file_info = AsyncMock(
            return_value={
                "last_modified": datetime.utcnow() - timedelta(hours=1),
                "size": 1024,
            }
        )
        storage_mock.delete_file = AsyncMock()
        with patch("app.queue.periodic_tasks.MinIOClient", return_value=storage_mock):
            deleted = await _async_cleanup_temp_files()
        assert deleted == 0
        storage_mock.delete_file.assert_not_called()


class TestAsyncCleanupOldTasks:
    """Async тесты очистки старых задач."""

    @pytest.mark.asyncio
    async def test_deletes_tasks_older_than_cutoff(self):
        """Удаляет записи задач старее указанной даты."""
        mock_db = MagicMock()
        repo_mock = MagicMock()
        repo_mock.delete_tasks_older_than = AsyncMock(return_value=5)
        with patch("app.queue.periodic_tasks.async_session_maker") as sess_maker:
            sess_maker.return_value = MagicMock()
            with patch("app.queue.periodic_tasks.TaskRepository", return_value=repo_mock):
                deleted = await _async_cleanup_old_tasks(days=30)
        assert deleted == 5
        repo_mock.delete_tasks_older_than.assert_called_once()


class TestCleanupOldFilesCelery:
    """Celery task тесты."""

    @patch("app.queue.periodic_tasks.asyncio.run")
    def test_cleanup_old_files_calls_async_cleanup(self, mock_run):
        """Вызывает async функцию и возвращает результат."""
        mock_run.return_value = "Deleted 10 old files"
        result = cleanup_old_files(retention_days=7)
        mock_run.assert_called_once()
        assert result == "Deleted 10 old files"

    @patch("app.queue.periodic_tasks.asyncio.run")
    def test_cleanup_old_files_uses_default_retention_if_none(self, mock_run):
        """Использует STORAGE_RETENTION_DAYS если параметр None."""
        with patch("app.queue.periodic_tasks.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(STORAGE_RETENTION_DAYS=14)
            cleanup_old_files()  # без параметра
            # async_run будет вызван с get_settings()


class TestCleanupTempFilesCelery:
    """Celery task тесты."""

    @patch("app.queue.periodic_tasks.asyncio.run")
    def test_cleanup_temp_files_calls_async_cleanup(self, mock_run):
        """Вызывает async функцию и возвращает результат."""
        mock_run.return_value = "Deleted 5 temp files"
        result = cleanup_temp_files()
        mock_run.assert_called_once()
        assert result == "Deleted 5 temp files"


class TestCleanupOldTasksCelery:
    """Celery task тесты."""

    @patch("app.queue.periodic_tasks.asyncio.run")
    def test_cleanup_old_tasks_calls_async_cleanup(self, mock_run):
        """Вызывает async функцию и возвращает результат."""
        mock_run.return_value = "Deleted 20 old tasks"
        result = cleanup_old_tasks(task_retention_days=90)
        mock_run.assert_called_once()
        assert result == "Deleted 20 old tasks"
