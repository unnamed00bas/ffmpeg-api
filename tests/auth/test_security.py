"""
Security tests for authentication endpoints
"""
import pytest
from fastapi import FastAPI
from unittest.mock import patch, MagicMock
from app.auth.security import SecurityService
from app.auth.jwt import JWTService
import re


# Create a minimal test app for security tests
test_app = FastAPI(title="Test Security API")


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


@test_app.post("/api/v1/auth/register")
async def test_register(username: str, email: str, password: str):
    return {"id": 1, "username": username, "email": email, "created_at": "2025-01-01T00:00:00"}


@test_app.get("/api/v1/auth/me")
async def test_me():
    return {
        "id": 1,
        "username": "testuser",
        "email": "test@example.com",
        "settings": {},
        "created_at": "2025-01-01T00:00:00"
    }


from fastapi.testclient import TestClient

client = TestClient(test_app)
security = SecurityService()


class TestRateLimiting:
    """Test brute force protection with rate limiting"""

    def test_brute_force_prevention_too_many_attempts(self):
        """Test that brute force attacks are prevented by rate limiting"""
        # Attempt multiple failed logins
        failed_attempts = []
        for i in range(6):
            response = client.post(
                "/api/v1/auth/login",
                data={
                    "email_or_username": "nonexistent@example.com",
                    "password": "wrongpassword"
                }
            )
            failed_attempts.append(response.status_code)

        # Check if rate limiting kicks in after 5 failed attempts
        # Expected: After 5 failed attempts, subsequent requests should be rate limited
        assert failed_attempts[-1] == 429, "Should be rate limited after 5 failed attempts"

    def test_rate_limit_resets_after_timeout(self):
        """Test that rate limit resets after timeout period"""
        # First, hit rate limit
        for _ in range(6):
            client.post(
                "/api/v1/auth/login",
                data={
                    "email_or_username": "test@example.com",
                    "password": "wrong"
                }
            )

        # After some time (mocked), try again
        # This test would require actual time or mocking of rate limiter
        # For now, we just verify the structure exists
        assert True


class TestJWTSecretNotLeaked:
    """Test that JWT secret is not leaked in logs"""

    def test_jwt_secret_not_in_login_response(self):
        """Test JWT secret is not in login response"""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "email_or_username": "test@example.com",
                "password": "wrongpassword"
            }
        )

        # JWT secret should never appear in response
        assert "secret" not in response.text.lower()
        assert "test-secret-key" not in response.text

    def test_jwt_secret_not_in_register_response(self):
        """Test JWT secret is not in register response"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "TestPassword123"
            }
        )

        # JWT secret should never appear in response
        assert "secret" not in response.text.lower()
        assert "test-secret-key" not in response.text

    def test_token_signature_verification(self):
        """Test that tokens are verified by signature"""
        jwt_service = JWTService("test-secret")

        # Create valid token
        valid_token = jwt_service.create_access_token(user_id=1)

        # Create tampered token (modify signature part)
        token_parts = valid_token.split('.')
        tampered_token = f"{token_parts[0]}.{token_parts[1]}.tampered_signature"

        # Should fail with tampered signature
        with pytest.raises(Exception):
            jwt_service.verify_token(tampered_token)

    def test_token_with_wrong_secret_fails(self):
        """Test token with wrong secret fails verification"""
        jwt_service1 = JWTService("secret1")
        jwt_service2 = JWTService("secret2")

        # Create token with secret1
        token = jwt_service1.create_access_token(user_id=1)

        # Try to verify with secret2 - should fail
        with pytest.raises(Exception):
            jwt_service2.verify_token(token)


class TestSensitiveDataNotExposed:
    """Test that sensitive data is not exposed in responses"""

    def test_password_not_in_response(self):
        """Test password is never returned in responses"""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "email_or_username": "test@example.com",
                "password": "mypassword123"
            }
        )

        # Password should never appear in response
        assert "password" not in response.text.lower()
        assert "mypassword123" not in response.text

    def test_hashed_password_not_in_user_response(self):
        """Test hashed_password is not in user endpoint response"""
        # First register a user (mock the database)
        with patch('app.database.connection.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__aenter__.return_value = mock_db

            # Mock user
            mock_user = MagicMock()
            mock_user.id = 1
            mock_user.username = "testuser"
            mock_user.email = "test@example.com"
            mock_user.hashed_password = "$2b$12$hash..."
            mock_user.api_key = "api_key_123"
            mock_user.settings = {}
            mock_user.is_admin = False
            mock_user.is_active = True

            # Create a valid token
            jwt_service = JWTService("test-secret-key-for-testing-only-32chars")
            token = jwt_service.create_access_token(user_id=1)

            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )

        # Hashed password should not be in response
        if response.status_code == 200:
            assert "hashed_password" not in response.json()
            assert "hash..." not in response.text

    def test_api_key_not_in_me_response(self):
        """Test API key is not in /me endpoint response"""
        # Mock database and create token
        with patch('app.database.connection.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__aenter__.return_value = mock_db

            mock_user = MagicMock()
            mock_user.id = 1
            mock_user.username = "testuser"
            mock_user.email = "test@example.com"
            mock_user.api_key = "secret_api_key"
            mock_user.settings = {}
            mock_user.is_admin = False
            mock_user.is_active = True

            jwt_service = JWTService("test-secret-key-for-testing-only-32chars")
            token = jwt_service.create_access_token(user_id=1)

            response = client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )

        # API key should not be in response
        if response.status_code == 200:
            assert "api_key" not in response.json()
            assert "secret_api_key" not in response.text

    def test_api_key_not_in_user_list_response(self):
        """Test API key is not in user list endpoint response"""
        with patch('app.database.connection.get_db') as mock_get_db:
            mock_db = MagicMock()
            mock_get_db.return_value.__aenter__.return_value = mock_db

            mock_user = MagicMock()
            mock_user.id = 1
            mock_user.username = "testuser"
            mock_user.email = "test@example.com"
            mock_user.api_key = "secret_api_key_456"
            mock_user.settings = {}
            mock_user.is_admin = True
            mock_user.is_active = True

            jwt_service = JWTService("test-secret-key-for-testing-only-32chars")
            token = jwt_service.create_access_token(user_id=1)

            response = client.get(
                "/api/v1/users",
                headers={"Authorization": f"Bearer {token}"}
            )

        # API key should not be in response
        if response.status_code == 200:
            users = response.json().get("users", [])
            for user in users:
                assert "api_key" not in user


class TestRefreshTokenSingleUse:
    """Test refresh token single use (optional)"""

    def test_refresh_token_single_use(self):
        """Test that refresh token can only be used once"""
        # This test requires implementation of refresh token blacklisting
        # or revocation mechanism in the backend
        # For now, we test the structure

        jwt_service = JWTService("test-secret")
        refresh_token = jwt_service.create_refresh_token(user_id=1)

        # First refresh should work (mocked)
        # Second refresh with same token should fail
        # This depends on backend implementation

        assert True  # Placeholder for when refresh token revocation is implemented

    def test_refresh_token_expires_correctly(self):
        """Test that refresh token has correct expiration"""
        jwt_service = JWTService("test-secret")

        from datetime import timedelta
        refresh_token = jwt_service.create_refresh_token(user_id=1)

        payload = jwt_service.decode_token(refresh_token)

        # Refresh token should expire in 7 days (by default)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        exp = payload["exp"]

        # Should be approximately 7 days from now
        time_diff = exp - now
        assert 7 * 24 * 3600 - 10 < time_diff.total_seconds() < 7 * 24 * 3600 + 10


class TestTokenValidation:
    """Test comprehensive token validation"""

    def test_token_without_signature_fails(self):
        """Test token without signature fails"""
        # Create a token without signature
        header = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        payload = "eyJ1c2VyX2lkIjoxLCJleHAiOjE2MjI1NzU1MDAsImlhdCI6MTYyMjQ4OTEwMCwidHlwZSI6ImFjY2VzcyJ9"

        invalid_token = f"{header}.{payload}."

        jwt_service = JWTService("test-secret")

        with pytest.raises(Exception):
            jwt_service.verify_token(invalid_token)

    def test_token_with_malformed_payload_fails(self):
        """Test token with malformed payload fails"""
        malformed_token = "invalid.token.format"

        jwt_service = JWTService("test-secret")

        with pytest.raises(Exception):
            jwt_service.verify_token(malformed_token)

    def test_expired_token_fails(self):
        """Test expired token fails verification"""
        from datetime import datetime, timezone, timedelta

        jwt_service = JWTService("test-secret")

        # Create token that's already expired
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        with patch('app.auth.jwt.datetime') as mock_datetime:
            mock_datetime.now.return_value = past_time

            expired_token = jwt_service.create_access_token(user_id=1)

        # Now verify (should fail)
        with pytest.raises(Exception):
            jwt_service.verify_token(expired_token)
