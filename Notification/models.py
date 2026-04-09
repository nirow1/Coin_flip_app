from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func, Enum
from sqlalchemy.orm import relationship
from db import Base
from Notification.enums import NotificationType


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(255), nullable=False)
    message = Column(String(1000), nullable=False)
    type = Column(Enum(NotificationType), nullable=False)

    is_read = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="notifications")
