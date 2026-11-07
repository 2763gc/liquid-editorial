from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Text
from app.db.base import Base

class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(Text, nullable=True, default="#FF4D2E")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    posts: Mapped[list["Post"]] = relationship("Post", secondary="post_tags", back_populates="tags")
