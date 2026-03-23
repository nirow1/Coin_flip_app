from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from Auth.models import User
from Auth.service import AuthService
from db import get_session

async def get_current_user(
    session: AsyncSession = Depends(get_session),
    token: str = Depends(AuthService.oauth2_scheme)
):
    user = await AuthService.get_current_user(token, session)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user

async def get_current_admin(user: User = Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user

