from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, Text, Index
from app.db.base import Base, TimestampMixin

class TIL(Base, TimestampMixin):
    """Today I Learned - 开发者每日知识切片 (PRD 5.8)"""
    __tablename__ = "til"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    tag: Mapped[str] = mapped_column(Text, nullable=False, index=True) # e.g. rust, vue, python, git
    content_md: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("idx_til_tag_created", "tag", "created_at"),
    )
