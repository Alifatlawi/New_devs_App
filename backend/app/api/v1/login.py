from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any
import logging
from datetime import datetime, timedelta
import jwt
from ...config import settings

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]
    error: Optional[str] = None


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login endpoint for local authentication"""
    try:
        email = request.email.lower().strip()
        password = request.password.strip()
        
        logger.info(f"[LOGIN] Attempting login for: {email}")
        
        # Static credentials - Tenant A.
        if email == "sunset@propertyflow.com" and password == "client_a_2024":
            logger.info("[LOGIN] Challenge Mode: Tenant A (Sunset Properties)")
            
            # Create mock JWT token
            user_data = {
                "id": "user-sunset",
                "email": "sunset@propertyflow.com",
                "app_metadata": {"role": "user", "tenant_id": "tenant-a"},
                "user_metadata": {"name": "Sunset Properties Manager"},
                "aud": "authenticated",
                "created_at": datetime.utcnow().isoformat(),
                "exp": datetime.utcnow() + timedelta(hours=24)
            }
            
            token = jwt.encode(user_data, settings.secret_key, algorithm="HS256")
            
            return LoginResponse(
                access_token=token,
                user={
                    "id": "user-sunset",
                    "email": "sunset@propertyflow.com",
                    "name": "Sunset Properties Manager",
                    "is_admin": False,
                    "tenant_id": "tenant-a",
                    "permissions": [],
                    "cities": []
                }
            )
            
        # Static credentials - Tenant B.
        if email == "ocean@propertyflow.com" and password == "client_b_2024":
            logger.info("[LOGIN] Challenge Mode: Tenant B (Ocean Rentals)")
            
            # Create mock JWT token
            user_data = {
                "id": "user-ocean",
                "email": "ocean@propertyflow.com",
                "app_metadata": {"role": "user", "tenant_id": "tenant-b"},
                "user_metadata": {"name": "Ocean Rentals Manager"},
                "aud": "authenticated",
                "created_at": datetime.utcnow().isoformat(),
                "exp": datetime.utcnow() + timedelta(hours=24)
            }
            
            token = jwt.encode(user_data, settings.secret_key, algorithm="HS256")
            
            return LoginResponse(
                access_token=token,
                user={
                    "id": "user-ocean",
                    "email": "ocean@propertyflow.com",
                    "name": "Ocean Rentals Manager",
                    "is_admin": False,
                    "tenant_id": "tenant-b",
                    "permissions": [],
                    "cities": []
                }
            )
        
        # Any other account is rejected. The previous fallback looked the email up in the
        # (mock) user list and issued a token without ever checking the password.
        logger.warning(f"[LOGIN] Invalid credentials for: {email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LOGIN] Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )


@router.post("/logout")
async def logout():
    """Logout endpoint"""
    # For JWT-based auth, logout is handled client-side by removing token
    return {"message": "Logged out successfully"}
