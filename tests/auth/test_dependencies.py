"""Unit tests for auth dependencies"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException, status

from app.auth.dependencies import (
    get_current_user,
    get_current_active_user,
    get_current_admin_user,
    require_api_key,
    get_optional_current_user
)
from app.database.models.user import User
from app.database.repositories.user_repository import UserRepository


@pytest.fixture
def mock_db():
    """Mock database session"""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Mock user object"""
    user = User(
        id=1,
        username="testuser",
        email="test@example.com",
        hashed_password="hashedpass",
        is_active=True,
        is_admin=False
    )
    return user


@pytest.fixture
def mock_admin_user():
    """Mock admin user object"""
    user = User(
        id=2,
        username="adminuser",
        email="admin@example.com",
        hashed_password="hashedpass",
        is_active=True,
        is_admin=True
    )
    return user


@pytest.fixture
def mock_inactive_user():
    """Mock inactive user object"""
    user = User(
        id=3,
        username="inactive",
        email="inactive@example.com",
        hashed_password="hashedpass",
        is_active=False,
        is_admin=False
    )
    return user


@pytest.fixture
def valid_token():
    """Valid JWT token"""
    from app.auth.dependencies import jwt_service
    return jwt_service.create_access_token(user_id=1)


@pytest.fixture
def admin_token():
    """Admin JWT token"""
    from app.auth.dependencies import jwt_service
    return jwt_service.create_access_token(user_id=2)


@pytest.fixture
def inactive_token():
    """Inactive user JWT token"""
    from app.auth.dependencies import jwt_service
    return jwt_service.create_access_token(user_id=3)


@pytest.mark.asyncio
class TestGetCurrentUser:
    """Tests for get_current_user dependency"""

    async def test_get_current_user_valid_token(self, mock_db, mock_user, valid_token):
        """Test get_current_user returns User from valid token"""
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_user)

        with patch('app.auth.dependencies.UserRepository', return_value=mock_repo):
            user = await get_current_user(token=valid_token, db=mock_db)

            assert user == mock_user
            mock_repo.get_by_id.assert_called_once_with(1)

    async def test_get_current_user_invalid_token(self, mock_db):
        """Test get_current_user raises HTTPException for invalid token"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token="invalid.token", db=mock_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in exc_info.value.detail

    async def test_get_current_user_not_found(self, mock_db, valid_token):
        """Test get_current_user raises HTTPException when user not found"""
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with patch('app.auth.dependencies.UserRepository', return_value=mock_repo):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token=valid_token, db=mock_db)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
class TestGetCurrentActiveUser:
    """Tests for get_current_active_user dependency"""

    async def test_get_current_active_user_active(self, mock_user):
        """Test get_current_active_user returns active user"""
        user = await get_current_active_user(current_user=mock_user)
        assert user == mock_user

    async def test_get_current_active_user_inactive(self, mock_inactive_user):
        """Test get_current_active_user raises HTTPException for inactive user"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_active_user(current_user=mock_inactive_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Inactive user" in exc_info.value.detail


@pytest.mark.asyncio
class TestGetCurrentAdminUser:
    """Tests for get_current_admin_user dependency"""

    async def test_get_current_admin_user_admin(self, mock_admin_user):
        """Test get_current_admin_user returns admin user"""
        user = await get_current_admin_user(current_user=mock_admin_user)
        assert user == mock_admin_user

    async def test_get_current_admin_user_non_admin(self, mock_user):
        """Test get_current_admin_user raises HTTPException for non-admin user"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(current_user=mock_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Not enough permissions" in exc_info.value.detail


@pytest.mark.asyncio
class TestRequireApiKey:
    """Tests for require_api_key dependency"""

    async def test_require_api_key_valid(self, mock_db, mock_user):
        """Test require_api_key returns User from valid API key"""
        mock_repo = AsyncMock()
        mock_repo.get_by_api_key = AsyncMock(return_value=mock_user)

        with patch('app.auth.dependencies.UserRepository', return_value=mock_repo):
            user = await require_api_key(api_key="valid-api-key", db=mock_db)

            assert user == mock_user
            mock_repo.get_by_api_key.assert_called_once_with("valid-api-key")

    async def test_require_api_key_missing(self, mock_db):
        """Test require_api_key raises HTTPException when API key is missing"""
        with pytest.raises(HTTPException) as exc_info:
            await require_api_key(api_key=None, db=mock_db)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "API key is missing" in exc_info.value.detail

    async def test_require_api_key_invalid(self, mock_db):
        """Test require_api_key raises HTTPException for invalid API key"""
        mock_repo = AsyncMock()
        mock_repo.get_by_api_key = AsyncMock(return_value=None)

        with patch('app.auth.dependencies.UserRepository', return_value=mock_repo):
            with pytest.raises(HTTPException) as exc_info:
                await require_api_key(api_key="invalid-key", db=mock_db)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid API key" in exc_info.value.detail

    async def test_require_api_key_inactive_user(self, mock_db, mock_inactive_user):
        """Test require_api_key raises HTTPException for inactive user"""
        mock_repo = AsyncMock()
        mock_repo.get_by_api_key = AsyncMock(return_value=mock_inactive_user)

        with patch('app.auth.dependencies.UserRepository', return_value=mock_repo):
            with pytest.raises(HTTPException) as exc_info:
                await require_api_key(api_key="valid-key", db=mock_db)

            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "Inactive user" in exc_info.value.detail


@pytest.mark.asyncio
class TestGetOptionalCurrentUser:
    """Tests for get_optional_current_user dependency"""

    async def test_get_optional_current_user_valid(self, mock_db, mock_user, valid_token):
        """Test get_optional_current_user returns User from valid token"""
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_user)

        with patch('app.auth.dependencies.UserRepository', return_value=mock_repo):
            user = await get_optional_current_user(token=valid_token, db=mock_db)

            assert user == mock_user

    async def test_get_optional_current_user_no_token(self, mock_db):
        """Test get_optional_current_user returns None when no token"""
        user = await get_optional_current_user(token=None, db=mock_db)
        assert user is None

    async def test_get_optional_current_user_invalid_token(self, mock_db):
        """Test get_optional_current_user returns None for invalid token"""
        user = await get_optional_current_user(token="invalid.token", db=mock_db)
        assert user is None
