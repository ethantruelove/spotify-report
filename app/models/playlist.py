from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models import UserID


class Playlist(Base):
    __tablename__ = "playlist"

    id: Mapped[int] = mapped_column(autoincrement=True)
    spotify_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("user_id.user_id"))

    user: Mapped["UserID"] = relationship(back_populates="playlists")
