from typing import TYPE_CHECKING

from sqlalchemy import Identity, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base

if TYPE_CHECKING:
    from app.models import Playlist


class UserID(Base):
    __tablename__ = "user_id"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    playlist: Mapped["Playlist"] = relationship(
        "Playlist",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
