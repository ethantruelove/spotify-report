from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Artist(Base):
    __tablename__ = "artist"

    spotify_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))

    def to_dict(self):
        return {
            "spotify_id": self.spotify_id,
            "name": self.name,
        }

    def __repr__(self):
        return f"<Artist spotify_id={self.spotify_id} name={self.name}>"


class ArtistSchema(BaseModel):
    spotify_id: str
    name: str
