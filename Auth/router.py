from fastapi import Depends

from Auth.schemas import RegisterRequest
from db import get_session


@router.post("/register")
async def register(request: RegisterRequest, session=Depends(get_session)):
    return await AuthService.register_user(request, session)