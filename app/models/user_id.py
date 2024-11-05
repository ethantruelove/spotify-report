from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from app.models import Base


class UserID(Base):
    __tablename__ = "user_id"

    id: int = Column(Integer, autoincrement=True)
    user_id: str = Column(String(50), primary_key=True)

    playlists = relationship("Playlist", back_populates="user_id")
