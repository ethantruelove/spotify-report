import datetime

from pydantic import BaseModel
from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Album(Base):
    __tablename__ = "album"

    spotify_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    artist_id: Mapped[str] = mapped_column(
        ForeignKey("artist.spotify_id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(200))
    release_date: Mapped[datetime.date] = mapped_column(Date(), nullable=True)

    def to_dict(self):
        return {
            "spotify_id": self.spotify_id,
            "artist_id": self.artist_id,
            "name": self.name,
            "release_date": self.release_date,
        }

    def __repr__(self):
        return (
            f"<Album spotify_id={self.spotify_id} artist_id={self.artist_id} "
            f"name={self.name} release_date={self.release_date}>"
        )


class AlbumSchema(BaseModel):
    spotify_id: str
    artist_id: str
    name: str
    release_date: datetime.date
