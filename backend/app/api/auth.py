from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
import logging
import jwt

from app.core.security import (
    get_db_context,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    SECRET_KEY,
    ALGORITHM
)
from app.database.models.user import User
from app.services.security_service import log_security_event

logger = logging.getLogger("it-agent-backend")

router = APIRouter(prefix="/auth", tags=["Authentication"])

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenRefreshRequest(BaseModel):
    refresh_token: str

@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db_context)):
    """Authenticates user and returns access and refresh tokens. Logs LOGIN or FAILED_LOGIN."""
    user = db.query(User).filter(User.username == payload.username).first()
    
    if not user or not verify_password(payload.password, user.hashed_password):
        from app.core.metrics import SECURITY_FAILED_LOGINS_TOTAL
        SECURITY_FAILED_LOGINS_TOTAL.labels(username=payload.username).inc()
        log_security_event(
            event_type="FAILED_LOGIN",
            username=payload.username,
            details="Incorrect username or password",
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
        
    if not user.is_active:
        from app.core.metrics import SECURITY_FAILED_LOGINS_TOTAL
        SECURITY_FAILED_LOGINS_TOTAL.labels(username=payload.username).inc()
        log_security_event(
            event_type="FAILED_LOGIN",
            username=payload.username,
            details="User account is deactivated",
            db=db
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated"
        )

    # Log successful login
    from app.core.metrics import SECURITY_LOGINS_TOTAL
    SECURITY_LOGINS_TOTAL.labels(username=user.username).inc()
    log_security_event(
        event_type="LOGIN",
        username=user.username,
        details=f"User logged in successfully with role '{user.role}'",
        db=db
    )


    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    }

@router.post("/refresh")
def refresh(payload: TokenRefreshRequest, db: Session = Depends(get_db_context)):
    """Verifies refresh token and returns a new access token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token"
    )
    try:
        decoded = decode_token(payload.refresh_token)
        username: str = decoded.get("sub")
        token_type: str = decoded.get("type")
        if username is None or token_type != "refresh":
            raise credentials_exception
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired"
        )
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise credentials_exception

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db_context)):
    """Logs the user logout event."""
    log_security_event(
        event_type="LOGOUT",
        username=current_user.username,
        details="User logged out successfully",
        db=db
    )
    return {"message": "Logged out successfully"}

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Returns details of the currently authenticated user."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at
    }
