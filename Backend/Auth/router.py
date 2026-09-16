from fastapi import APIRouter, Cookie, Depends, HTTPException, Response

from Backend.Auth.cookies import (
    clear_auth_cookies,
    set_access_cookie,
    set_csrf_cookie,
    set_refresh_cookie,
)
from Backend.Auth.dependencies import get_current_user
from Backend.Auth.models import User
from Backend.Auth.schemas import LoginRequest, RegisterRequest, UserResponse
from Backend.Auth.service import AuthService
from Backend.db import get_session

router = APIRouter()


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

    set_access_cookie(response, token["access_token"])
    set_refresh_cookie(response, token["refresh_token"])
    set_csrf_cookie(response, token["csrf_token"])

    return {"ok": True}


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)):
     return UserResponse(
        id=user.id,
        email=user.email,
        country=user.country,
        created_at=user.created_at,
    )


@router.post("/refresh")
async def refresh_tokens(response: Response,
                         refresh_token: str | None = Cookie(default=None),
                         session=Depends(get_session),
                         ):
    token = await AuthService.refresh_tokens(refresh_token, session)

    set_access_cookie(response, token["access_token"])
    set_csrf_cookie(response, token["csrf_token"])
    set_refresh_cookie(response, token["refresh_token"])
    return {"ok": True}


@router.post("/logout")
async def logout(
    response: Response,
    access_token: str | None = Cookie(default=None),
    refresh_token: str | None = Cookie(default=None),
    session=Depends(get_session),
):
    await AuthService.try_increment_token_version(access_token, refresh_token, session)
    clear_auth_cookies(response)
    return {"ok": True}
