"""
Unit tests for authentication API endpoints: register, login, get_me
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import status


class TestRegisterEndpoint:
    """Tests for user registration endpoint"""

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """Test successful user registration"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "SecurePass123"
            }
        )
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client, test_user):
        """Test registration with duplicate email returns 400"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "different",
                "email": test_user.email,
                "password": "SecurePass123"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Email already registered" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, client, test_user):
        """Test registration with duplicate username returns 400"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": test_user.username,
                "email": "different@example.com",
                "password": "SecurePass123"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Username already taken" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_register_invalid_password(self, client):
        """Test registration with weak password returns 400"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "weak"
            }
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.asyncio
    async def test_register_invalid_username_format(self, client):
        """Test registration with invalid username format returns 422"""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "invalid username!",
                "email": "newuser@example.com",
                "password": "SecurePass123"
            }
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestLoginEndpoint:
    """Tests for user login endpoint"""

    @pytest.mark.asyncio
    async def test_login_with_email_success(self, client, test_user):
        """Test successful login with email"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "TestPassword123"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data

    @pytest.mark.asyncio
    async def test_login_with_username_success(self, client, test_user):
        """Test successful login with username"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.username,
                "password": "TestPassword123"
            }
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, client):
        """Test login with non-existent email returns 401"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "TestPassword123"
            }
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Incorrect email/username or password" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_invalid_password(self, client, test_user):
        """Test login with wrong password returns 401"""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "WrongPassword123"
            }
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetMeEndpoint:
    """Tests for getting current user info endpoint"""

    @pytest.mark.asyncio
    async def test_get_me_unauthorized(self, client):
        """Test getting current user info without authentication returns 401"""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_get_me_authorized(self, authorized_client, test_user):
        """Test getting current user info with valid token"""
        response = await authorized_client.get("/api/v1/auth/me")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == test_user.id
        assert data["username"] == test_user.username
        assert data["email"] == test_user.email

    @pytest.mark.asyncio
    async def test_get_me_with_invalid_token(self, client):
        """Test getting current user info with invalid token returns 401"""
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestRefreshTokenEndpoint:
    """Tests for token refresh endpoint"""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client, test_user):
        """Test successful token refresh"""
        # First login to get tokens
        login_response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "TestPassword123"
            }
        )
        tokens = login_response.json()
        refresh_token = tokens["refresh_token"]

        # Refresh the token
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client):
        """Test refresh with invalid token returns 401"""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
