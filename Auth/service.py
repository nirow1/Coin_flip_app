from Auth.schemas import RegisterRequest, TokenResponse


class AuthService:
    @staticmethod
    async def register_user(data: RegisterRequest, session):
        ...

    @staticmethod
    async def authenticate_user(data):
        ...

    @staticmethod
    async def hash_password(data):
        ...

    @staticmethod
    async def verify_password(data):
        ...

    @staticmethod
    async def create_access_token(data) -> TokenResponse:
        ...