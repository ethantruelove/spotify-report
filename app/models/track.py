from typing import TYPE_CHECKING, Self

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
        ForeignKey("playlist.spotify_id", ondelete="CASCADE")
    )
    artist_id: Mapped[str] = mapped_column(
        ForeignKey("artist.spotify_id", ondelete="SET NULL"), nullable=True
    )
    album_id: Mapped[str] = mapped_column(
        ForeignKey("album.spotify_id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(250))

    playlist: Mapped["Playlist"] = relationship(back_populates="track")

    def to_dict(self):
        return {
            "id": self.id,
            "spotify_id": self.spotify_id,
            "playlist_id": self.playlist_id,
            "album_id": self.album_id,
            "artist_id": self.artist_id,
            "name": self.name,
        }

    def __repr__(self):
        return (
            f"<Track id={self.id} spotify_id={self.spotify_id} playlist_id={self.playlist_id} "
            f"artist_id={self.artist_id} album_id={self.album_id} name={self.name}>"
        )

    def __eq__(self, track: Self):
        return (
            self.id == track.id
            and self.spotify_id == track.spotify_id
            and self.playlist_id == track.playlist_id
            and self.artist_id == track.artist_id
            and self.album_id == track.album_id
            and self.name == track.name
        )


class TrackSchema(BaseModel):
    spotify_id: str
    album_id: str
    artist_id: str
    name: str
