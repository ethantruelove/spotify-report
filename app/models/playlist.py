from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models import UserID


class Playlist(Base):
    __tablename__ = "playlist"

    spotify_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_id.user_id", ondelete="SET NULL")
    )

    user: Mapped["UserID"] = relationship(back_populates="playlist")


class PlaylistSchema(BaseModel):
    spotify_id: str
    user_id: str
