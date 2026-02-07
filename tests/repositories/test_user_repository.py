"""
Unit tests for UserRepository
"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.repositories.user_repository import UserRepository
from app.database.models.user import User
from app.auth.security import SecurityService


@pytest.mark.asyncio
class TestUserRepository:
    """Tests for UserRepository"""

    async def test_create_user_success(self, test_db: AsyncSession):
        """Test successful user creation"""
        repo = UserRepository(test_db)
        security = SecurityService()

        user = await repo.create(
            username="newuser",
            email="newuser@example.com",
            hashed_password=security.hash_password("Password123")
        )

        assert user is not None
        assert user.username == "newuser"
        assert user.email == "newuser@example.com"
        assert user.is_active is True
        assert user.is_admin is False

    async def test_get_by_id_success(self, test_db: AsyncSession, test_user: User):
        """Test getting user by ID"""
        repo = UserRepository(test_db)

        user = await repo.get_by_id(test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.username == test_user.username

    async def test_get_by_id_not_found(self, test_db: AsyncSession):
        """Test getting non-existent user by ID"""
        repo = UserRepository(test_db)

        user = await repo.get_by_id(99999)

        assert user is None

    async def test_get_by_username_success(self, test_db: AsyncSession, test_user: User):
        """Test getting user by username"""
        repo = UserRepository(test_db)

        user = await repo.get_by_username(test_user.username)

        assert user is not None
        assert user.username == test_user.username
        assert user.id == test_user.id

    async def test_get_by_username_not_found(self, test_db: AsyncSession):
        """Test getting non-existent user by username"""
        repo = UserRepository(test_db)

        user = await repo.get_by_username("nonexistent")

        assert user is None

    async def test_get_by_email_success(self, test_db: AsyncSession, test_user: User):
        """Test getting user by email"""
        repo = UserRepository(test_db)

        user = await repo.get_by_email(test_user.email)

        assert user is not None
        assert user.email == test_user.email
        assert user.id == test_user.id

    async def test_get_by_email_not_found(self, test_db: AsyncSession):
        """Test getting non-existent user by email"""
        repo = UserRepository(test_db)

        user = await repo.get_by_email("nonexistent@example.com")

        assert user is None

    async def test_update_user_success(self, test_db: AsyncSession, test_user: User):
        """Test updating user"""
        repo = UserRepository(test_db)

        updated = await repo.update(
            test_user.id,
            {"is_active": False}
        )

        assert updated is True

        # Verify update
        await test_db.refresh(test_user)
        assert test_user.is_active is False

    async def test_update_user_not_found(self, test_db: AsyncSession):
        """Test updating non-existent user"""
        repo = UserRepository(test_db)

        updated = await repo.update(
            99999,
            {"is_active": False}
        )

        assert updated is False

    async def test_delete_user_success(self, test_db: AsyncSession, test_user: User):
        """Test deleting user"""
        repo = UserRepository(test_db)

        deleted = await repo.delete(test_user.id)

        assert deleted is True

        # Verify deletion
        user = await repo.get_by_id(test_user.id)
        assert user is None

    async def test_delete_user_not_found(self, test_db: AsyncSession):
        """Test deleting non-existent user"""
        repo = UserRepository(test_db)

        deleted = await repo.delete(99999)

        assert deleted is False

    async def test_list_users_success(self, test_db: AsyncSession, test_user: User):
        """Test listing users"""
        repo = UserRepository(test_db)

        users = await repo.list(limit=10, offset=0)

        assert isinstance(users, list)
        assert len(users) > 0
        assert any(u.id == test_user.id for u in users)

    async def test_list_users_pagination(self, test_db: AsyncSession):
        """Test listing users with pagination"""
        repo = UserRepository(test_db)

        users = await repo.list(limit=1, offset=0)

        assert len(users) <= 1

    async def test_count_users(self, test_db: AsyncSession):
        """Test counting users"""
        repo = UserRepository(test_db)

        count = await repo.count()

        assert isinstance(count, int)
        assert count >= 1

    async def test_verify_password_success(self, test_db: AsyncSession, test_user: User):
        """Test password verification"""
        repo = UserRepository(test_db)
        security = SecurityService()

        user = await repo.get_by_id(test_user.id)
        verified = security.verify_password(
            "TestPassword123",
            user.hashed_password
        )

        assert verified is True

    async def test_verify_password_failure(self, test_db: AsyncSession, test_user: User):
        """Test password verification with wrong password"""
        repo = UserRepository(test_db)
        security = SecurityService()

        user = await repo.get_by_id(test_user.id)
        verified = security.verify_password(
            "WrongPassword123",
            user.hashed_password
        )

        assert verified is False
