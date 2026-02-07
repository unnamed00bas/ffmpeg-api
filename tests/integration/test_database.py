"""
Integration tests for database
"""
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from app.database.models.base import Base


@pytest.mark.integration
class TestDatabaseIntegration:
    """Integration tests for database"""

    @pytest.fixture
    async def test_engine(self):
        """Create test database engine"""
        # Use PostgreSQL for integration tests
        engine = create_async_engine(
            "postgresql+asyncpg://postgres:postgres@localhost:5432/ffmpeg_api_test"
        )

        yield engine

        await engine.dispose()

    @pytest.fixture
    async def test_session(self, test_engine):
        """Create test database session"""
        async_session = async_sessionmaker(
            test_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        async with async_session() as session:
            yield session

    @pytest.mark.asyncio
    async def test_connection(self, test_engine):
        """Test database connection"""
        async with test_engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1

    @pytest.mark.asyncio
    async def test_create_tables(self, test_engine):
        """Test table creation"""
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Check that tables exist
        async with test_engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
            """))
            tables = [row[0] for row in result.fetchall()]

            assert "users" in tables
            assert "tasks" in tables
            assert "files" in tables
            assert "operation_logs" in tables
            assert "metrics" in tables

    @pytest.mark.asyncio
    async def test_transaction_rollback(self, test_session):
        """Test transaction rollback"""
        from app.database.models.user import User
        from app.auth.security import SecurityService

        security = SecurityService()

        # Create user
        user = User(
            username="rollback_test",
            email="rollback@test.com",
            hashed_password=security.hash_password("test123"),
            is_active=True
        )

        test_session.add(user)

        # Rollback
        await test_session.rollback()

        # Verify user was not saved
        result = await test_session.execute(
            select(User).where(User.username == "rollback_test")
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_transaction_commit(self, test_session):
        """Test transaction commit"""
        from app.database.models.user import User
        from app.auth.security import SecurityService

        security = SecurityService()

        # Create user
        user = User(
            username="commit_test",
            email="commit@test.com",
            hashed_password=security.hash_password("test123"),
            is_active=True
        )

        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        # Verify user was saved
        result = await test_session.execute(
            select(User).where(User.username == "commit_test")
        )
        saved_user = result.scalar_one_or_none()

        assert saved_user is not None
        assert saved_user.username == "commit_test"
        assert saved_user.email == "commit@test.com"

    @pytest.mark.asyncio
    async def test_insert_user(self, test_session):
        """Test inserting a user"""
        from app.database.models.user import User
        from app.auth.security import SecurityService

        security = SecurityService()

        user = User(
            username="insert_test",
            email="insert@test.com",
            hashed_password=security.hash_password("test123"),
            is_active=True
        )

        test_session.add(user)
        await test_session.commit()

        assert user.id is not None

    @pytest.mark.asyncio
    async def test_select_user(self, test_session):
        """Test selecting a user"""
        from app.database.models.user import User
        from app.auth.security import SecurityService

        security = SecurityService()

        # Create user
        user = User(
            username="select_test",
            email="select@test.com",
            hashed_password=security.hash_password("test123"),
            is_active=True
        )

        test_session.add(user)
        await test_session.commit()

        # Select user
        result = await test_session.execute(
            select(User).where(User.username == "select_test")
        )
        selected_user = result.scalar_one()

        assert selected_user is not None
        assert selected_user.username == "select_test"

    @pytest.mark.asyncio
    async def test_update_user(self, test_session):
        """Test updating a user"""
        from app.database.models.user import User
        from app.auth.security import SecurityService

        security = SecurityService()

        # Create user
        user = User(
            username="update_test",
            email="update@test.com",
            hashed_password=security.hash_password("test123"),
            is_active=True
        )

        test_session.add(user)
        await test_session.commit()

        # Update user
        user.is_active = False
        await test_session.commit()

        # Verify update
        result = await test_session.execute(
            select(User).where(User.username == "update_test")
        )
        updated_user = result.scalar_one()

        assert updated_user.is_active is False

    @pytest.mark.asyncio
    async def test_delete_user(self, test_session):
        """Test deleting a user"""
        from app.database.models.user import User
        from app.auth.security import SecurityService
        from sqlalchemy import delete

        security = SecurityService()

        # Create user
        user = User(
            username="delete_test",
            email="delete@test.com",
            hashed_password=security.hash_password("test123"),
            is_active=True
        )

        test_session.add(user)
        await test_session.commit()

        # Delete user
        await test_session.execute(
            delete(User).where(User.username == "delete_test")
        )
        await test_session.commit()

        # Verify deletion
        result = await test_session.execute(
            select(User).where(User.username == "delete_test")
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_foreign_key_constraint(self, test_session):
        """Test foreign key constraints"""
        from app.database.models.file import File
        from app.database.models.user import User
        from app.auth.security import SecurityService
        from datetime import datetime

        security = SecurityService()

        # Create user
        user = User(
            username="fk_test",
            email="fk@test.com",
            hashed_password=security.hash_password("test123"),
            is_active=True
        )
        test_session.add(user)
        await test_session.commit()

        # Create file referencing user
        file = File(
            user_id=user.id,
            filename="test.mp4",
            original_filename="test.mp4",
            size=1024,
            content_type="video/mp4",
            storage_path="/test/test.mp4",
            metadata={},
            is_deleted=False,
            created_at=datetime.utcnow()
        )
        test_session.add(file)
        await test_session.commit()

        assert file.id is not None
        assert file.user_id == user.id

    @pytest.mark.asyncio
    async def test_unique_constraint(self, test_session):
        """Test unique constraints"""
        from app.database.models.user import User
        from app.auth.security import SecurityService
        from sqlalchemy.exc import IntegrityError

        security = SecurityService()

        # Create first user
        user1 = User(
            username="unique_test",
            email="unique@test.com",
            hashed_password=security.hash_password("test123"),
            is_active=True
        )
        test_session.add(user1)
        await test_session.commit()

        # Try to create duplicate user
        user2 = User(
            username="unique_test",  # Same username
            email="unique2@test.com",
            hashed_password=security.hash_password("test123"),
            is_active=True
        )
        test_session.add(user2)

        # Should raise IntegrityError
        with pytest.raises(IntegrityError):
            await test_session.commit()
