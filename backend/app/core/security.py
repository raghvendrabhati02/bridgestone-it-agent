import os
import logging
from datetime import datetime, timedelta
from typing import List
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models.user import User

logger = logging.getLogger("it-agent-backend")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "bridgestone-it-agent-super-secret-key-123456")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# OAuth2 scheme for extracting Bearer tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(password: str, hashed_password: str) -> bool:
    """Verifies a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.error("Error verifying password: %s", e)
        return False

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict, expires_delta: timedelta = None) -> str:
    """Creates a JWT refresh token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    """Decodes and validates a JWT token. Raises PyJWT exceptions on invalid/expired tokens."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

# Database dependency (custom local provider to avoid circular imports in security dependencies)
def get_db_context():
    try:
        from app.core.metrics import DB_CONNECTIONS_ACTIVE
        DB_CONNECTIONS_ACTIVE.inc()
    except Exception:
        pass
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        try:
            from app.core.metrics import DB_CONNECTIONS_ACTIVE
            DB_CONNECTIONS_ACTIVE.dec()
        except Exception:
            pass

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db_context)) -> User:
    """FastAPI dependency to retrieve the current authenticated user."""
    from app.core.metrics import SECURITY_JWT_EXPIRED_TOTAL, SECURITY_UNAUTHORIZED_TOTAL

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        SECURITY_UNAUTHORIZED_TOTAL.inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(token)
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        if username is None or token_type != "access":
            SECURITY_UNAUTHORIZED_TOTAL.inc()
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        SECURITY_JWT_EXPIRED_TOTAL.inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        SECURITY_UNAUTHORIZED_TOTAL.inc()
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        SECURITY_UNAUTHORIZED_TOTAL.inc()
        raise credentials_exception
    if not user.is_active:
        SECURITY_UNAUTHORIZED_TOTAL.inc()
        raise HTTPException(status_code=400, detail="User account is inactive")

    # Populate logging context variables
    from app.core.logging_context import user_ctx, role_ctx
    user_ctx.set(user.username)
    role_ctx.set(user.role)

    return user

class RoleChecker:
    """Dependency helper to verify roles and log permission denials."""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user), db: Session = Depends(get_db_context)) -> User:
        if current_user.role not in self.allowed_roles:
            from app.core.metrics import SECURITY_PERMISSION_DENIED_TOTAL
            SECURITY_PERMISSION_DENIED_TOTAL.labels(username=current_user.username).inc()
            
            # Import dynamically to prevent circular dependencies
            try:
                from app.services.security_service import log_security_event
                log_security_event(
                    event_type="PERMISSION_DENIED",
                    username=current_user.username,
                    details=f"User attempted to access restricted route with role '{current_user.role}'. Required roles: {self.allowed_roles}",
                    db=db
                )
            except Exception as e:
                logger.error("Failed to log permission denied security event: %s", e)
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource"
            )
        return current_user

