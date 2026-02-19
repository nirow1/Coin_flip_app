from pydantic import BaseModel, EmailStr
from datetime import date, datetime

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    country: str
    dob: date

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    country: str
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
