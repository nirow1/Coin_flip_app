from pydantic import BaseModel


class FriendResponse(BaseModel):
    id: int
    user_id: int
    friend_id: int
    status: str

    model_config = {"from_attributes": True}


class UserSearchResponse(BaseModel):
    id: int
    username: str | None

    model_config = {"from_attributes": True}

