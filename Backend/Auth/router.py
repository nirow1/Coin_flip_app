from fastapi import APIRouter, Depends, HTTPException, Response

from Backend.Auth.dependencies import get_current_user
from Backend.Auth.models import User
from Backend.Auth.schemas import LoginRequest, RegisterRequest, UserResponse
from Backend.Auth.service import AuthService
from Backend.config import settings
from Backend.db import get_session

router = APIRouter()


def _cookie_secure() -> bool:
    """Use Secure cookies when any CORS origin is https (production)."""
    return any(
        origin.strip().startswith("https://")
        for origin in settings.CORS_ORIGINS.split(",")
    )


@router.post("/register")
async def register(request: RegisterRequest, session=Depends(get_session)):
    try:
        return await AuthService.register_user(request, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(
    request: LoginRequest,
    response: Response,
    session=Depends(get_session),
):
    try:
        token = await AuthService.login_user(request, session)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )
    return {"ok": True}

@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
     return UserResponse(
        id=user.id,
        email=user.email,
        country=user.country,
        created_at=user.created_at,
    )

@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="lax",
        secure=_cookie_secure(),
    )
    return {"ok": True}
