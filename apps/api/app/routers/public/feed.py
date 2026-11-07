from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.models.post import Post

router = APIRouter(prefix="/feed", tags=["feed"])

@router.get("")
async def get_feed_data(db: AsyncSession = Depends(get_db)):
    query = (
        select(Post)
        .where(Post.status == "published", Post.visibility == "public", Post.deleted_at.is_(None))
        .order_by(desc(Post.published_at))
        .limit(20)
    )
    result = await db.execute(query)
    posts = result.scalars().all()

    items = []
    for p in posts:
        items.append({
            "title": p.title,
            "slug": p.slug,
            "url": f"/posts/{p.slug}",
            "description": p.excerpt,
            "content_md": p.content_md,
            "published_at": p.published_at,
            "updated_at": p.content_updated_at or p.published_at,
        })
    return items
