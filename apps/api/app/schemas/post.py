from typing import Any
from pydantic import BaseModel, ConfigDict
from app.schemas.tag import TagOut

class CoverOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    url: str
    width: int | None = None
    height: int | None = None
    dominant_color: str | None = None
    lqip: str | None = None
    alt: str | None = None

class TocItem(BaseModel):
    level: int
    text: str
    anchor: str

class SeriesBrief(BaseModel):
    slug: str
    title: str
    order: int | None = None
    total: int | None = None

class PostNavBrief(BaseModel):
    slug: str
    title: str

class PostListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    number: int | None = None
    title: str
    subtitle: str | None = None
    excerpt: str | None = None
    cover: CoverOut | None = None
    layout_variant: str = "standard"
    accent_color: str | None = None
    tags: list[TagOut] = []
    word_count: int = 0
    reading_minutes: int = 1
    view_count: int = 0
    like_count: int = 0
    is_pinned: bool = False
    published_at: str | None = None

class PostDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    number: int | None = None
    title: str
    subtitle: str | None = None
    excerpt: str | None = None
    content_md: str
    toc: list[TocItem] = []
    cover: CoverOut | None = None
    layout_variant: str = "standard"
    accent_color: str | None = None
    tags: list[TagOut] = []
    series: SeriesBrief | None = None
    word_count: int = 0
    reading_minutes: int = 1
    view_count: int = 0
    like_count: int = 0
    liked: bool = False
    comment_count: int = 0
    allow_comments: bool = True
    published_at: str | None = None
    content_updated_at: str | None = None
    prev: PostNavBrief | None = None
    next: PostNavBrief | None = None
