from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Text
from app.db.base import Base

class Series(Base):
    __tablename__ = "series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_media_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, default="ongoing", nullable=False) # ongoing / completed
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    posts: Mapped[list["Post"]] = relationship("Post", back_populates="series_rel")
