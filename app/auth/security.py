"""Security service for password hashing and API key generation"""
import re
import secrets
from passlib.context import CryptContext


class SecurityService:
    """Service for security operations"""

    # Common weak passwords to check against
    WEAK_PASSWORDS = [
        "password", "123456", "12345678", "qwerty", "abc123",
        "monkey", "password1", "password123", "1234567890", "admin",
        "welcome", "login", "letmein", "password!", "Password1",
        "Admin123", "password!", "Welcome1", "Login123", "Letmein123",
        "Qwerty123", "Abc12345", "Monkey123", "Welcome123", "Admin1234",
        "Password12", "12345678", "qwertyuiop", "asdfgh", "zxcvbn",
        "111111", "123123", "123qwe", "qwerty123", "123abc",
        "admin123", "root", "toor", "pass", "test", "user"
    ]

    def __init__(self):
        """Initialize security service with bcrypt context"""
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt

        Args:
            password: Plain text password

        Returns:
            Hashed password string

        Raises:
            ValueError: If password is too weak
        """
        # Validate password strength before hashing
        self.validate_password_strength(password)

        # Truncate password to 72 bytes (bcrypt limitation)
        # Bcrypt only uses the first 72 bytes of the password
        password_bytes = password.encode('utf-8')
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
            password = password_bytes.decode('utf-8')

        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hashed password

        Args:
            plain_password: Plain text password
            hashed_password: Hashed password

        Returns:
            True if password matches, False otherwise
        """
        return self.pwd_context.verify(plain_password, hashed_password)

    def generate_api_key(self) -> str:
        """
        Generate a secure API key

        Returns:
            URL-safe random string (32+ characters)
        """
        return secrets.token_urlsafe(32)

    def validate_password_strength(self, password: str) -> None:
        """
        Validate password strength

        Args:
            password: Password to validate

        Raises:
            ValueError: If password doesn't meet requirements
        """
        errors = []

        # Check minimum length
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")

        # Check for uppercase letter
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")

        # Check for lowercase letter
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")

        # Check for digit
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")

        # Check for special character (optional but recommended)
        # if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        #     errors.append("Password must contain at least one special character")

        # Check for common weak passwords
        if password.lower() in self.WEAK_PASSWORDS:
            errors.append("Password is too common and weak")

        if errors:
            raise ValueError("; ".join(errors))

    def is_strong_password(self, password: str) -> bool:
        """
        Check if password meets strength requirements

        Args:
            password: Password to check

        Returns:
            True if password is strong, False otherwise
        """
        try:
            self.validate_password_strength(password)
            return True
        except ValueError:
            return False

    def validate_email(self, email: str) -> bool:
        """
        Validate email format

        Args:
            email: Email address to validate

        Returns:
            True if email is valid, False otherwise
        """
        # Improved email regex pattern that prevents consecutive dots and invalid formats
        pattern = r'^[a-zA-Z0-9](?:[a-zA-Z0-9._%+-]*[a-zA-Z0-9])?@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        # Additional checks for edge cases
        if not email:
            return False

        # Check for consecutive dots
        if '..' in email:
            return False

        # Check for dot at start or end of local part
        local_part = email.split('@')[0]
        if local_part.startswith('.') or local_part.endswith('.'):
            return False

        return re.match(pattern, email) is not None

    def generate_reset_token(self) -> str:
        """
        Generate a secure token for password reset

        Returns:
            URL-safe random string
        """
        return secrets.token_urlsafe(32)

    def generate_verification_token(self) -> str:
        """
        Generate a secure token for email verification

        Returns:
            URL-safe random string
        """
        return secrets.token_urlsafe(32)
