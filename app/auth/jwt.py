"""JWT service for token creation and validation"""
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from jose import JWTError, jwt
from pydantic import BaseModel


class TokenPayload(BaseModel):
    """Token payload model"""
    user_id: int
    exp: datetime
    iat: datetime
    type: str = "access"  # access or refresh


class JWTService:
    """Service for JWT token operations"""

    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        """
        Initialize JWT service

        Args:
            secret_key: Secret key for signing tokens
            algorithm: Algorithm to use for token encoding (default: HS256)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create_access_token(self, user_id: int, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create an access token

        Args:
            user_id: User ID
            expires_delta: Custom expiration time (default: 30 minutes)

        Returns:
            JWT access token string
        """
        now = datetime.now(timezone.utc)
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(minutes=30)

        to_encode = {
            "user_id": user_id,
            "exp": expire,
            "iat": now,
            "type": "access"
        }

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def create_refresh_token(self, user_id: int, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a refresh token

        Args:
            user_id: User ID
            expires_delta: Custom expiration time (default: 7 days)

        Returns:
            JWT refresh token string
        """
        now = datetime.now(timezone.utc)
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(days=7)

        to_encode = {
            "user_id": user_id,
            "exp": expire,
            "iat": now,
            "type": "refresh"
        }

        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def verify_token(self, token: str) -> TokenPayload:
        """
        Verify and decode a token

        Args:
            token: JWT token string

        Returns:
            TokenPayload object

        Raises:
            JWTError: If token is invalid or expired
        """
        try:
            payload = self.decode_token(token)
            return TokenPayload(**payload)
        except JWTError as e:
            raise JWTError(f"Invalid token: {str(e)}")

    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode a token without full validation

        Args:
            token: JWT token string

        Returns:
            Dictionary with token payload

        Raises:
            JWTError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            raise JWTError(f"Could not validate credentials: {str(e)}")

    def get_user_id_from_token(self, token: str) -> int:
        """
        Extract user ID from token

        Args:
            token: JWT token string

        Returns:
            User ID

        Raises:
            JWTError: If token is invalid or user_id not found
        """
        payload = self.verify_token(token)
        if payload.user_id is None:
            raise JWTError("Token does not contain user_id")
        return payload.user_id

    def is_refresh_token(self, token: str) -> bool:
        """
        Check if token is a refresh token

        Args:
            token: JWT token string

        Returns:
            True if refresh token, False otherwise
        """
        try:
            payload = self.decode_token(token)
            return payload.get("type") == "refresh"
        except JWTError:
            return False

    def is_access_token(self, token: str) -> bool:
        """
        Check if token is an access token

        Args:
            token: JWT token string

        Returns:
            True if access token, False otherwise
        """
        try:
            payload = self.decode_token(token)
            return payload.get("type") == "access"
        except JWTError:
            return False
