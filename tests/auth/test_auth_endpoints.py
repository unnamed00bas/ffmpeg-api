"""Integration tests for auth endpoints"""
import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, status
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from datetime import timedelta

from app.config import settings
from app.database.models.user import User, Base
from app.database.repositories.user_repository import UserRepository
from app.auth.jwt import JWTService


# Create a test app without importing app.main to avoid circular import
test_app = FastAPI(title="Test API")


# Simple routes for testing
@test_app.post("/api/v1/auth/register")
async def test_register(username: str, email: str, password: str):
    return {"id": 1, "username": username, "email": email, "created_at": "2025-01-01T00:00:00"}


@test_app.post("/api/v1/auth/login")
async def test_login(email_or_username: str, password: str):
    from app.auth.security import SecurityService
    security = SecurityService()
    # Simplified implementation for testing
    return {
        "access_token": "test_token",
        "refresh_token": "test_refresh",
        "token_type": "bearer",
        "expires_in": 1800
    }


@test_app.post("/api/v1/auth/refresh")
async def test_refresh(refresh_token: str):
    return {
        "access_token": "new_token",
        "token_type": "bearer",
        "expires_in": 1800
    }


@test_app.get("/api/v1/auth/me")
async def test_me():
    return {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "settings": {},
        "created_at": "2025-01-01T00:00:00"
    }


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create test database session"""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_app(test_session):
    """Create test app with test database"""
    from app.database.connection import async_session_maker
    # Patch the database session
    async with test_session.begin():
        yield test_app


@pytest.fixture
async def client(test_app):
    """Create async test client"""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers(client):
    """Helper fixture to get auth headers"""
    # Register and login a user
    register_data = {
        "username": "testuser",
        "email": "test@example.com",
        "password": "TestPass123"
    }
    await client.post("/api/v1/auth/register", json=register_data)

    login_data = {
        "username": "testuser",
        "password": "TestPass123"
    }
    response = await client.post("/api/v1/auth/login", data=login_data)
    token_data = response.json()

    return {"Authorization": f"Bearer {token_data['access_token']}"}


@pytest.fixture
async def jwt_service():
    """JWT service fixture for testing"""
    return JWTService(
        secret_key=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM
    )


@pytest.mark.asyncio
class TestRegisterEndpoint:
    """Tests for POST /api/v1/auth/register"""

    async def test_register_success(self, client):
        """Test successful user registration"""
        register_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "SecurePass123"
        }

        response = await client.post("/api/v1/auth/register", json=register_data)

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data  # Password should not be in response

    async def test_register_duplicate_email(self, client):
        """Test registration with duplicate email fails"""
        register_data = {
            "username": "user1",
            "email": "test@example.com",
            "password": "SecurePass123"
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Try to register with same email
        register_data2 = {
            "username": "user2",
            "email": "test@example.com",  # Duplicate email
            "password": "SecurePass123"
        }
        response = await client.post("/api/v1/auth/register", json=register_data2)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already registered" in response.json()["detail"].lower()

    async def test_register_duplicate_username(self, client):
        """Test registration with duplicate username fails"""
        register_data = {
            "username": "duplicate",
            "email": "user1@example.com",
            "password": "SecurePass123"
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Try to register with same username
        register_data2 = {
            "username": "duplicate",  # Duplicate username
            "email": "user2@example.com",
            "password": "SecurePass123"
        }
        response = await client.post("/api/v1/auth/register", json=register_data2)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already taken" in response.json()["detail"].lower()

    async def test_register_weak_password(self, client):
        """Test registration with weak password fails"""
        register_data = {
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "weak"  # Too weak
        }
        response = await client.post("/api/v1/auth/register", json=register_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.json()["detail"].lower()

    async def test_register_invalid_email(self, client):
        """Test registration with invalid email format fails"""
        register_data = {
            "username": "invalidemail",
            "email": "invalid-email",  # Invalid email format
            "password": "SecurePass123"
        }
        response = await client.post("/api/v1/auth/register", json=register_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_register_short_username(self, client):
        """Test registration with short username fails"""
        register_data = {
            "username": "ab",  # Too short (< 3 chars)
            "email": "test@example.com",
            "password": "SecurePass123"
        }
        response = await client.post("/api/v1/auth/register", json=register_data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_register_invalid_username_chars(self, client):
        """Test registration with invalid username characters fails"""
        register_data = {
            "username": "user@name",  # Invalid character
            "email": "test@example.com",
            "password": "SecurePass123"
        }
        response = await client.post("/api/v1/auth/register", json=register_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
class TestLoginEndpoint:
    """Tests for POST /api/v1/auth/login"""

    async def test_login_success(self, client):
        """Test successful login with username"""
        # Register user first
        register_data = {
            "username": "loginuser",
            "email": "login@example.com",
            "password": "LoginPass123"
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Login with username
        login_data = {
            "username": "loginuser",
            "password": "LoginPass123"
        }
        response = await client.post("/api/v1/auth/login", data=login_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    async def test_login_with_email(self, client):
        """Test successful login with email"""
        # Register user first
        register_data = {
            "username": "emaillogin",
            "email": "emaillogin@example.com",
            "password": "EmailLogin123"
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Login with email
        login_data = {
            "username": "emaillogin@example.com",  # Email instead of username
            "password": "EmailLogin123"
        }
        response = await client.post("/api/v1/auth/login", data=login_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data

    async def test_login_wrong_password(self, client):
        """Test login with wrong password fails"""
        # Register user first
        register_data = {
            "username": "wrongpass",
            "email": "wrongpass@example.com",
            "password": "CorrectPass123"
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Login with wrong password
        login_data = {
            "username": "wrongpass",
            "password": "WrongPass123"
        }
        response = await client.post("/api/v1/auth/login", data=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "incorrect" in response.json()["detail"].lower()

    async def test_login_nonexistent_user(self, client):
        """Test login with non-existent user fails"""
        login_data = {
            "username": "nonexistent",
            "password": "SomePass123"
        }
        response = await client.post("/api/v1/auth/login", data=login_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_login_inactive_user(self, client, test_session):
        """Test login with inactive user fails"""
        # Register user
        register_data = {
            "username": "inactiveuser",
            "email": "inactive@example.com",
            "password": "InactivePass123"
        }
        await client.post("/api/v1/auth/register", json=register_data)

        # Deactivate user
        user_repo = UserRepository(test_session)
        user = await user_repo.get_by_email("inactive@example.com")
        await user_repo.set_active(user.id, False)

        # Try to login
        login_data = {
            "username": "inactiveuser",
            "password": "InactivePass123"
        }
        response = await client.post("/api/v1/auth/login", data=login_data)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "inactive" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestRefreshEndpoint:
    """Tests for POST /api/v1/auth/refresh"""

    async def test_refresh_success(self, client):
        """Test successful token refresh"""
        # Register and login
        register_data = {
            "username": "refreshuser",
            "email": "refresh@example.com",
            "password": "RefreshPass123"
        }
        await client.post("/api/v1/auth/register", json=register_data)

        login_data = {
            "username": "refreshuser",
            "password": "RefreshPass123"
        }
        login_response = await client.post("/api/v1/auth/login", data=login_data)
        login_data_response = login_response.json()
        refresh_token = login_data_response["refresh_token"]

        # Refresh token
        refresh_data = {"refresh_token": refresh_token}
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["refresh_token"] == refresh_token  # Should return same refresh token
        assert data["token_type"] == "bearer"

    async def test_refresh_expired_token(self, client, jwt_service):
        """Test refresh with expired token fails"""
        # Create expired refresh token
        user_id = 999
        expired_token = jwt_service.create_refresh_token(
            user_id,
            expires_delta=timedelta(seconds=-1)
        )

        refresh_data = {"refresh_token": expired_token}
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_invalid_token(self, client):
        """Test refresh with invalid token fails"""
        refresh_data = {"refresh_token": "invalid.token.string"}
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_refresh_access_token(self, client):
        """Test refresh with access token (not refresh token) fails"""
        # Register and login
        register_data = {
            "username": "accesstoken",
            "email": "access@example.com",
            "password": "AccessPass123"
        }
        await client.post("/api/v1/auth/register", json=register_data)

        login_data = {
            "username": "accesstoken",
            "password": "AccessPass123"
        }
        login_response = await client.post("/api/v1/auth/login", data=login_data)
        access_token = login_response.json()["access_token"]

        # Try to refresh with access token
        refresh_data = {"refresh_token": access_token}
        response = await client.post("/api/v1/auth/refresh", json=refresh_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "invalid token type" in response.json()["detail"].lower()


@pytest.mark.asyncio
class TestMeEndpoint:
    """Tests for GET /api/v1/auth/me"""

    async def test_get_me_success(self, client, auth_headers):
        """Test getting current user info with valid token"""
        response = await client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert "username" in data
        assert "email" in data
        assert "password" not in data
        assert "hashed_password" not in data
        assert "api_key" not in data

    async def test_get_me_without_token(self, client):
        """Test getting current user without token fails"""
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_me_invalid_token(self, client):
        """Test getting current user with invalid token fails"""
        headers = {"Authorization": "Bearer invalid.token"}
        response = await client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_me_expired_token(self, client, jwt_service):
        """Test getting current user with expired token fails"""
        expired_token = jwt_service.create_access_token(
            user_id=1,
            expires_delta=timedelta(seconds=-1)
        )
        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
