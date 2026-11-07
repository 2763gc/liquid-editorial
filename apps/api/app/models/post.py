from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Text, Float, ForeignKey, CheckConstraint, Index
from app.db.base import Base, TimestampMixin

class PostTag(Base):
    __tablename__ = "post_tags"

    post_id: Mapped[int] = mapped_column(Integer, ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True)

class Post(Base, TimestampMixin):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    number: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    toc_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reading_minutes: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    cover_media_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("media.id", ondelete="SET NULL"), nullable=True)
    og_media_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("media.id", ondelete="SET NULL"), nullable=True)

    layout_variant: Mapped[str] = mapped_column(
        Text, 
        default="standard", 
        nullable=False
    )
    accent_color: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text, 
        default="draft", 
        nullable=False
    )
    visibility: Mapped[str] = mapped_column(
        Text, 
        default="public", 
        nullable=False
    )
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_featured: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_pinned: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    allow_comments: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    series_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("series.id", ondelete="SET NULL"), nullable=True)
    series_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    canvas_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    canvas_y: Mapped[float | None] = mapped_column(Float, nullable=True)

    seo_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    seo_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    published_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_updated_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 关联关系
    tags: Mapped[list["Tag"]] = relationship("Tag", secondary="post_tags", back_populates="posts")
    cover: Mapped["Media | None"] = relationship("Media", foreign_keys=[cover_media_id])
    series_rel: Mapped["Series | None"] = relationship("Series", back_populates="posts")

    __table_args__ = (
        CheckConstraint(
            "layout_variant IN ('standard', 'wide', 'immersive', 'essay', 'showcase')",
            name="check_layout_variant"
        ),
        CheckConstraint(
            "status IN ('draft', 'scheduled', 'published', 'archived')",
            name="check_status"
        ),
        CheckConstraint(
            "visibility IN ('public', 'unlisted', 'password')",
            name="check_visibility"
        ),
        Index("idx_posts_status_published", "status", "published_at"),
        Index("idx_posts_featured", "is_featured"),
    )
