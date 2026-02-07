"""Unit tests for Security service"""
import pytest

from app.auth.security import SecurityService


@pytest.fixture
def security_service():
    """Security service fixture"""
    return SecurityService()


class TestSecurityService:
    """Tests for SecurityService"""

    def test_hash_password(self, security_service):
        """Test hash_password creates a hash"""
        password = "Secure123"
        hashed = security_service.hash_password(password)

        assert hashed is not None
        assert isinstance(hashed, str)
        assert hashed != password  # Hash should be different from password
        assert len(hashed) > 50  # Bcrypt hashes are typically 60 chars

    def test_hash_password_same_input_different_output(self, security_service):
        """Test hash_password produces different hashes for same input"""
        password = "Secure123"
        hash1 = security_service.hash_password(password)
        hash2 = security_service.hash_password(password)

        assert hash1 != hash2  # Different salts produce different hashes

    def test_verify_password_correct(self, security_service):
        """Test verify_password returns True for correct password"""
        password = "Secure123"
        hashed = security_service.hash_password(password)

        assert security_service.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self, security_service):
        """Test verify_password returns False for incorrect password"""
        password = "Secure123"
        wrong_password = "Wrong123"
        hashed = security_service.hash_password(password)

        assert security_service.verify_password(wrong_password, hashed) is False

    def test_generate_api_key(self, security_service):
        """Test generate_api_key creates a unique key"""
        api_key = security_service.generate_api_key()

        assert api_key is not None
        assert isinstance(api_key, str)
        assert len(api_key) >= 32  # Minimum 32 characters
        assert len(api_key) <= 128  # Reasonable upper bound

    def test_generate_api_key_unique(self, security_service):
        """Test generate_api_key creates unique keys"""
        key1 = security_service.generate_api_key()
        key2 = security_service.generate_api_key()

        assert key1 != key2

    def test_validate_password_strength_valid(self, security_service):
        """Test validate_password_strength accepts valid passwords"""
        valid_passwords = [
            "SecurePass123",
            "MyPassword1",
            "Test1234",
            "ComplexPass9",
        ]

        for password in valid_passwords:
            # Should not raise exception
            security_service.validate_password_strength(password)

    def test_validate_password_strength_too_short(self, security_service):
        """Test validate_password_strength rejects short passwords"""
        short_passwords = ["Pass1", "123", "A1b"]

        for password in short_passwords:
            with pytest.raises(ValueError) as exc_info:
                security_service.validate_password_strength(password)
            assert "at least 8 characters" in str(exc_info.value)

    def test_validate_password_strength_no_uppercase(self, security_service):
        """Test validate_password_strength rejects passwords without uppercase"""
        passwords = ["lowercase1", "testpass123", "noupper1"]

        for password in passwords:
            with pytest.raises(ValueError) as exc_info:
                security_service.validate_password_strength(password)
            assert "uppercase" in str(exc_info.value)

    def test_validate_password_strength_no_lowercase(self, security_service):
        """Test validate_password_strength rejects passwords without lowercase"""
        passwords = ["UPPERCASE1", "TESTPASS123", "NOLOWER1"]

        for password in passwords:
            with pytest.raises(ValueError) as exc_info:
                security_service.validate_password_strength(password)
            assert "lowercase" in str(exc_info.value)

    def test_validate_password_strength_no_digit(self, security_service):
        """Test validate_password_strength rejects passwords without digits"""
        passwords = ["NoDigits", "Password", "TestPassword"]

        for password in passwords:
            with pytest.raises(ValueError) as exc_info:
                security_service.validate_password_strength(password)
            assert "digit" in str(exc_info.value)

    def test_validate_password_strength_weak_password(self, security_service):
        """Test validate_password_strength rejects common weak passwords"""
        # These are all in the WEAK_PASSWORDS list
        weak_passwords = ["Password1", "Password123", "Admin123", "Welcome1"]

        for password in weak_passwords:
            with pytest.raises(ValueError) as exc_info:
                security_service.validate_password_strength(password)
            assert "weak" in str(exc_info.value).lower() or "common" in str(exc_info.value).lower()

    def test_is_strong_password(self, security_service):
        """Test is_strong_password returns correct boolean"""
        assert security_service.is_strong_password("SecurePass123") is True
        assert security_service.is_strong_password("weak1") is False
        assert security_service.is_strong_password("weakpassword") is False

    def test_validate_email_valid(self, security_service):
        """Test validate_email accepts valid emails"""
        valid_emails = [
            "test@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user123@example.co.uk",
            "test.user@test-domain.com",
        ]

        for email in valid_emails:
            assert security_service.validate_email(email) is True

    def test_validate_email_invalid(self, security_service):
        """Test validate_email rejects invalid emails"""
        invalid_emails = [
            "invalid",
            "@example.com",
            "test@",
            "test@.com",
            "test..email@example.com",
            "",
            "test example.com",
        ]

        for email in invalid_emails:
            assert security_service.validate_email(email) is False

    def test_generate_reset_token(self, security_service):
        """Test generate_reset_token creates a token"""
        token = security_service.generate_reset_token()

        assert token is not None
        assert isinstance(token, str)
        assert len(token) >= 32

    def test_generate_verification_token(self, security_service):
        """Test generate_verification_token creates a token"""
        token = security_service.generate_verification_token()

        assert token is not None
        assert isinstance(token, str)
        assert len(token) >= 32

    def test_tokens_are_unique(self, security_service):
        """Test that different token generation methods create unique values"""
        api_key1 = security_service.generate_api_key()
        api_key2 = security_service.generate_api_key()
        reset_token = security_service.generate_reset_token()
        verify_token = security_service.generate_verification_token()

        assert api_key1 != api_key2
        assert api_key1 != reset_token
        assert api_key1 != verify_token
        assert reset_token != verify_token
