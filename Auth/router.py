from fastapi import Depends, APIRouter, HTTPException

from Auth.schemas import RegisterRequest, LoginRequest
from Auth.service import AuthService
from db import get_session

router  = APIRouter()

@router.post("/register")
async def register(request: RegisterRequest, session=Depends(get_session)):
    try:
        return await AuthService.register_user(request, session)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/login")
async def login(request: LoginRequest, session=Depends(get_session)):
    try:
        return await AuthService.login_user(request, session)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
