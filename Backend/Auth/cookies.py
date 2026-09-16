from fastapi import Response

from Backend.config import settings


def set_access_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


def set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.JWT_REFRESH_EXPIRE_DAYS * 24 * 60 * 60,
        path="/auth",
    )


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )
    response.delete_cookie(
        key="refresh_token",
        path="/auth",
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )
