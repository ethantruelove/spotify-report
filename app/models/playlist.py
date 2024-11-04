from sqlalchemy import Column, ForeignKey, Integer, String

from app.models.base import Base
from app.models.user_id import User


class Playlist(Base):
    __tablename__ = "playlist"

    id: int = Column(Integer, autoincrement=True)
    spotify_id: str = Column(String(50), primary_key=True)
    user_id: str = Column(String(50), ForeignKey("user_id.user_id"))
