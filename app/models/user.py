from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    username  = Column(String(50), primary_key=True)
    password  = Column(String(255), nullable=False)
    # role: "user" | "admin"
    role      = Column(String(10), default="user", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

