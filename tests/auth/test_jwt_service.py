"""Unit tests for JWT service"""
import pytest
from datetime import datetime, timedelta
from jose import JWTError

from app.auth.jwt import JWTService, TokenPayload


@pytest.fixture
def jwt_service():
    """JWT service fixture"""
    return JWTService(secret_key="test-secret-key-for-testing-purposes")


class TestJWTService:
    """Tests for JWTService"""

    def test_create_access_token(self, jwt_service):
        """Test create_access_token creates a valid JWT token"""
        user_id = 1
        token = jwt_service.create_access_token(user_id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token can be decoded
        payload = jwt_service.verify_token(token)
        assert payload.user_id == user_id
        assert payload.type == "access"

    def test_create_access_token_with_custom_expiry(self, jwt_service):
        """Test create_access_token with custom expiration"""
        user_id = 2
        expires_delta = timedelta(hours=1)

        token = jwt_service.create_access_token(user_id, expires_delta)
        payload = jwt_service.verify_token(token)

        assert payload.user_id == user_id
        # Check expiration is approximately 1 hour from now
        from datetime import timezone
        now = datetime.now(timezone.utc)
        assert payload.exp > now + timedelta(minutes=58)
        assert payload.exp < now + timedelta(minutes=62)

    def test_create_refresh_token(self, jwt_service):
        """Test create_refresh_token creates a valid refresh token"""
        user_id = 3
        token = jwt_service.create_refresh_token(user_id)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

        payload = jwt_service.verify_token(token)
        assert payload.user_id == user_id
        assert payload.type == "refresh"

    def test_create_refresh_token_with_custom_expiry(self, jwt_service):
        """Test create_refresh_token with custom expiration"""
        user_id = 4
        expires_delta = timedelta(days=30)

        token = jwt_service.create_refresh_token(user_id, expires_delta)
        payload = jwt_service.verify_token(token)

        assert payload.user_id == user_id
        assert payload.type == "refresh"

    def test_verify_token_valid_token(self, jwt_service):
        """Test verify_token validates a correct token"""
        user_id = 5
        token = jwt_service.create_access_token(user_id)

        payload = jwt_service.verify_token(token)
        assert isinstance(payload, TokenPayload)
        assert payload.user_id == user_id
        assert isinstance(payload.exp, datetime)
        assert isinstance(payload.iat, datetime)

    def test_verify_token_invalid_token(self, jwt_service):
        """Test verify_token raises exception for invalid token"""
        with pytest.raises(JWTError):
            jwt_service.verify_token("invalid.token.string")

    def test_verify_token_expired_token(self, jwt_service):
        """Test verify_token raises exception for expired token"""
        user_id = 6
        # Create token that expires immediately
        expires_delta = timedelta(seconds=-1)
        token = jwt_service.create_access_token(user_id, expires_delta)

        with pytest.raises(JWTError):
            jwt_service.verify_token(token)

    def test_verify_token_wrong_secret(self):
        """Test verify_token raises exception for token with wrong secret"""
        service1 = JWTService(secret_key="secret1")
        service2 = JWTService(secret_key="secret2")

        token = service1.create_access_token(1)

        with pytest.raises(JWTError):
            service2.verify_token(token)

    def test_decode_token(self, jwt_service):
        """Test decode_token returns token payload"""
        user_id = 7
        token = jwt_service.create_access_token(user_id)

        payload = jwt_service.decode_token(token)
        assert isinstance(payload, dict)
        assert payload["user_id"] == user_id
        assert "exp" in payload
        assert "iat" in payload
        assert payload["type"] == "access"

    def test_decode_token_invalid(self, jwt_service):
        """Test decode_token raises exception for invalid token"""
        with pytest.raises(JWTError):
            jwt_service.decode_token("invalid.token")

    def test_get_user_id_from_token(self, jwt_service):
        """Test get_user_id_from_token extracts user ID"""
        user_id = 8
        token = jwt_service.create_access_token(user_id)

        extracted_id = jwt_service.get_user_id_from_token(token)
        assert extracted_id == user_id

    def test_get_user_id_from_token_invalid(self, jwt_service):
        """Test get_user_id_from_token raises exception for invalid token"""
        with pytest.raises(JWTError):
            jwt_service.get_user_id_from_token("invalid.token")

    def test_is_refresh_token(self, jwt_service):
        """Test is_refresh_token returns True for refresh tokens"""
        refresh_token = jwt_service.create_refresh_token(1)
        access_token = jwt_service.create_access_token(1)

        assert jwt_service.is_refresh_token(refresh_token) is True
        assert jwt_service.is_refresh_token(access_token) is False

    def test_is_access_token(self, jwt_service):
        """Test is_access_token returns True for access tokens"""
        refresh_token = jwt_service.create_refresh_token(1)
        access_token = jwt_service.create_access_token(1)

        assert jwt_service.is_access_token(access_token) is True
        assert jwt_service.is_access_token(refresh_token) is False

    def test_token_with_different_algorithms(self):
        """Test tokens created with different algorithms are compatible"""
        service_hs256 = JWTService(secret_key="secret", algorithm="HS256")
        user_id = 10

        token = service_hs256.create_access_token(user_id)
        payload = service_hs256.verify_token(token)
        assert payload.user_id == user_id
