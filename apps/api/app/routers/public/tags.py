from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.tag import Tag
from app.models.post import Post
from app.schemas.tag import TagOut
from app.schemas.post import PostListItem, CoverOut

router = APIRouter(prefix="/tags", tags=["tags"])

@router.get("", response_model=list[TagOut])
async def list_tags(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Tag).order_by(Tag.name))
    tags = result.scalars().all()
    return tags

@router.get("/{slug}")
async def get_tag_detail(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Tag).where(Tag.slug == slug)
    )
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(status_code=404, detail="标签不存在")

    posts_query = (
        select(Post)
        .options(selectinload(Post.tags), selectinload(Post.cover))
        .join(Post.tags)
        .where(
            Tag.id == tag.id,
            Post.status == "published",
            Post.visibility == "public",
            Post.deleted_at.is_(None)
        )
        .order_by(Post.published_at.desc())
    )
    posts_res = (await db.execute(posts_query)).scalars().all()

    items = []
    for p in posts_res:
        cover_out = None
        if p.cover:
            cover_out = CoverOut(
                url=p.cover.url,
                width=p.cover.width,
                height=p.cover.height,
                dominant_color=p.cover.dominant_color,
                lqip=p.cover.lqip,
                alt=p.cover.alt,
            )
        items.append(
            PostListItem(
                id=p.id,
                slug=p.slug,
                number=p.number,
                title=p.title,
                subtitle=p.subtitle,
                excerpt=p.excerpt,
                cover=cover_out,
                layout_variant=p.layout_variant,
                accent_color=p.accent_color,
                tags=p.tags,
                word_count=p.word_count,
                reading_minutes=p.reading_minutes,
                view_count=p.view_count,
                published_at=p.published_at,
            )
        )

    return {
        "tag": TagOut.model_validate(tag),
        "posts": items,
        "total": len(items)
    }
