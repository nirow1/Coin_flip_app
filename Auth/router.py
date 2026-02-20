from fastapi import Depends, APIRouter

from Auth.schemas import RegisterRequest, LoginRequest
from Auth.service import AuthService
from db import get_session

router  = APIRouter()

@router.post("/register")
async def register(request: RegisterRequest, session=Depends(get_session)):
    return await AuthService.register_user(request, session)

async def login(request: LoginRequest, session=Depends(get_session)):
    return await AuthService.login_user(request, session)