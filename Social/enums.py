import enum


class FriendStatus(enum.Enum):
    NONE = 0
    PENDING = 1
    ACCEPTED = 2
    BLOCKED = 3