from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import ForeignKey, Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models import Playlist


class Track(Base):
    __tablename__ = "track"

    id: Mapped[int] = mapped_column(
        Integer, Identity(start=1, increment=1), primary_key=True
    )
    spotify_id: Mapped[str] = mapped_column(String(50))
    playlist_id: Mapped[str] = mapped_column(
        ForeignKey("playlist.spotify_id", ondelete="SET NULL")
    )
    album_id: Mapped[str] = mapped_column(String(50))
    artist_id: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))

    playlist: Mapped["Playlist"] = relationship(back_populates="track")


class TrackSchema(BaseModel):
    spotify_id: str
    album_id: str
    artist_id: str
    name: str
