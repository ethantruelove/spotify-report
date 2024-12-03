from typing import TYPE_CHECKING, Self

from pydantic import BaseModel
from sqlalchemy import String
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

    def to_dict(self):
        return {"user_id": self.user_id}

    def __repr__(self):
        return f"<UserID user_id={self.user_id}>"

    def __eq__(self, user: Self):
        return self.user_id == user.user_id


class UserIDSchema(BaseModel):
    user_id: str
