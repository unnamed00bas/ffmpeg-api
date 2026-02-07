"""
Unit tests for FileRepository
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories.file_repository import FileRepository
from app.database.models.file import File
from datetime import datetime


@pytest.mark.asyncio
class TestFileRepository:
    """Tests for FileRepository"""

    async def test_create_file_success(self, test_db: AsyncSession, test_user):
        """Test successful file creation"""
        repo = FileRepository(test_db)

        file = await repo.create(
            user_id=test_user.id,
            filename="test_file.mp4",
            original_filename="test_file.mp4",
            size=1024000,
            content_type="video/mp4",
            storage_path="/test/path/test_file.mp4",
            metadata={"duration": 120, "resolution": "1920x1080"}
        )

        assert file is not None
        assert file.user_id == test_user.id
        assert file.filename == "test_file.mp4"
        assert file.original_filename == "test_file.mp4"
        assert file.size == 1024000
        assert file.content_type == "video/mp4"
        assert file.is_deleted is False

    async def test_get_by_id_success(self, test_db: AsyncSession, test_file: File):
        """Test getting file by ID"""
        repo = FileRepository(test_db)

        file = await repo.get_by_id(test_file.id)

        assert file is not None
        assert file.id == test_file.id
        assert file.filename == test_file.filename

    async def test_get_by_id_not_found(self, test_db: AsyncSession):
        """Test getting non-existent file by ID"""
        repo = FileRepository(test_db)

        file = await repo.get_by_id(99999)

        assert file is None

    async def test_get_by_user_id_success(
        self,
        test_db: AsyncSession,
        test_file: File,
        test_user
    ):
        """Test getting files by user ID"""
        repo = FileRepository(test_db)

        files = await repo.get_by_user_id(test_user.id)

        assert isinstance(files, list)
        assert len(files) > 0
        assert any(f.id == test_file.id for f in files)

    async def test_get_by_user_id_exclude_deleted(
        self,
        test_db: AsyncSession,
        test_file: File,
        test_user
    ):
        """Test getting files by user ID excluding deleted"""
        repo = FileRepository(test_db)

        # Mark file as deleted
        test_file.is_deleted = True
        await test_db.commit()

        files = await repo.get_by_user_id(test_user.id, include_deleted=False)

        assert not any(f.id == test_file.id for f in files)

    async def test_get_by_user_id_with_pagination(
        self,
        test_db: AsyncSession,
        test_user
    ):
        """Test getting files by user ID with pagination"""
        repo = FileRepository(test_db)

        files = await repo.get_by_user_id(
            test_user.id,
            limit=5,
            offset=0
        )

        assert len(files) <= 5

    async def test_count_by_user_id_success(
        self,
        test_db: AsyncSession,
        test_file: File,
        test_user
    ):
        """Test counting files by user ID"""
        repo = FileRepository(test_db)

        count = await repo.count_by_user_id(test_user.id)

        assert isinstance(count, int)
        assert count >= 1

    async def test_update_file_success(
        self,
        test_db: AsyncSession,
        test_file: File
    ):
        """Test updating file"""
        repo = FileRepository(test_db)

        updated = await repo.update(
            test_file.id,
            {"metadata": {"duration": 240, "resolution": "3840x2160"}}
        )

        assert updated is True

        # Verify update
        await test_db.refresh(test_file)
        assert test_file.metadata["duration"] == 240

    async def test_update_file_not_found(self, test_db: AsyncSession):
        """Test updating non-existent file"""
        repo = FileRepository(test_db)

        updated = await repo.update(
            99999,
            {"metadata": {}}
        )

        assert updated is False

    async def test_mark_as_deleted_success(
        self,
        test_db: AsyncSession,
        test_file: File
    ):
        """Test marking file as deleted"""
        repo = FileRepository(test_db)

        await repo.mark_as_deleted(test_file.id)

        # Verify deletion
        await test_db.refresh(test_file)
        assert test_file.is_deleted is True
        assert test_file.deleted_at is not None

    async def test_mark_as_deleted_not_found(self, test_db: AsyncSession):
        """Test marking non-existent file as deleted"""
        repo = FileRepository(test_db)

        # Should not raise error
        await repo.mark_as_deleted(99999)

    async def test_delete_file_permanent_success(
        self,
        test_db: AsyncSession,
        test_file: File
    ):
        """Test permanent deletion of file"""
        repo = FileRepository(test_db)

        deleted = await repo.delete(test_file.id)

        assert deleted is True

        # Verify deletion
        file = await repo.get_by_id(test_file.id)
        assert file is None

    async def test_delete_file_permanent_not_found(self, test_db: AsyncSession):
        """Test permanent deletion of non-existent file"""
        repo = FileRepository(test_db)

        deleted = await repo.delete(99999)

        assert deleted is False

    async def test_get_storage_path_success(
        self,
        test_db: AsyncSession,
        test_file: File
    ):
        """Test getting storage path"""
        repo = FileRepository(test_db)

        path = await repo.get_storage_path(test_file.id)

        assert path == test_file.storage_path

    async def test_get_storage_path_not_found(self, test_db: AsyncSession):
        """Test getting storage path of non-existent file"""
        repo = FileRepository(test_db)

        path = await repo.get_storage_path(99999)

        assert path is None

    async def test_get_old_deleted_files(
        self,
        test_db: AsyncSession,
        test_file: File
    ):
        """Test getting old deleted files"""
        repo = FileRepository(test_db)

        # Mark file as deleted with old date
        test_file.is_deleted = True
        test_file.deleted_at = datetime.utcnow() - timedelta(days=40)
        await test_db.commit()

        old_files = await repo.get_old_deleted_files(days=30)

        assert len(old_files) >= 1
        assert any(f.id == test_file.id for f in old_files)

    async def test_list_all_files_success(
        self,
        test_db: AsyncSession,
        test_file: File
    ):
        """Test listing all files"""
        repo = FileRepository(test_db)

        files = await repo.list_all(limit=10, offset=0)

        assert isinstance(files, list)
        assert len(files) > 0
        assert any(f.id == test_file.id for f in files)

    async def test_list_all_files_with_pagination(self, test_db: AsyncSession):
        """Test listing all files with pagination"""
        repo = FileRepository(test_db)

        files = await repo.list_all(limit=1, offset=0)

        assert len(files) <= 1

    async def test_count_all_files(self, test_db: AsyncSession):
        """Test counting all files"""
        repo = FileRepository(test_db)

        count = await repo.count_all()

        assert isinstance(count, int)
        assert count >= 1

    async def test_get_total_storage_by_user(
        self,
        test_db: AsyncSession,
        test_file: File,
        test_user
    ):
        """Test getting total storage used by user"""
        repo = FileRepository(test_db)

        total = await repo.get_total_storage_by_user(test_user.id)

        assert isinstance(total, int)
        assert total >= test_file.size

    async def test_get_files_by_content_type(
        self,
        test_db: AsyncSession,
        test_file: File,
        test_user
    ):
        """Test getting files by content type"""
        repo = FileRepository(test_db)

        files = await repo.get_by_content_type(
            test_user.id,
            "video/mp4"
        )

        assert isinstance(files, list)
        assert all(f.content_type == "video/mp4" for f in files)
