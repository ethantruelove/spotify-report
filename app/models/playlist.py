from typing import TYPE_CHECKING, Self

from pydantic import BaseModel
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models import Track, UserID


class Playlist(Base):
    __tablename__ = "playlist"

    spotify_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("user_id.user_id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(200))

    user: Mapped["UserID"] = relationship(back_populates="playlist")
    track: Mapped["Track"] = relationship(
        back_populates="playlist", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "spotify_id": self.spotify_id,
            "user_id": self.user_id,
            "name": self.name,
        }

    def __repr__(self):
        return f"<Playlist spotify_id={self.spotify_id} user_id={self.user_id} name={self.name}>"

    def __eq__(self, playlist: Self):
        return (
            self.spotify_id == playlist.spotify_id
            and self.user_id == playlist.user_id
            and self.name == playlist.name
        )


class PlaylistSchema(BaseModel):
    spotify_id: str
    user_id: str
