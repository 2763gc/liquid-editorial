from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, Text
from app.db.base import Base, TimestampMixin

class FriendLink(Base, TimestampMixin):
    """友链与同行列表 (PRD 5.12)"""
    __tablename__ = "friend_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    avatar: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(Text, default="tech", nullable=False) # tech / friend / inspiration
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
