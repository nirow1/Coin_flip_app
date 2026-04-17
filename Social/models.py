from sqlalchemy import Column, Integer, ForeignKey, Enum
from sqlalchemy.orm import relationship
from Social.enums import FriendStatus
from db import Base


class Friend(Base):
    __tablename__ = 'FriendsList'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    friend_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    status = Column(Enum(FriendStatus), nullable=False)

    user = relationship("User", back_populates="friends", foreign_keys=[user_id])
