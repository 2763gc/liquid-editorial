from collections import defaultdict
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.models.post import Post

router = APIRouter(prefix="/archive", tags=["archive"])

@router.get("")
async def get_archive_data(db: AsyncSession = Depends(get_db)):
    query = (
        select(Post.id, Post.slug, Post.number, Post.title, Post.published_at, Post.word_count, Post.layout_variant)
        .where(Post.status == "published", Post.visibility == "public", Post.deleted_at.is_(None))
        .order_by(desc(Post.published_at))
    )
    result = await db.execute(query)
    posts = result.all()

    total_words = sum(p.word_count for p in posts)
    total_posts = len(posts)

    # 按年份分组
    years_dict = defaultdict(list)
    for p in posts:
        year = (p.published_at or "2026")[:4]
        month = (p.published_at or "2026-01")[5:7]
        years_dict[year].append({
            "id": p.id,
            "slug": p.slug,
            "number": p.number,
            "title": p.title,
            "date": (p.published_at or "").split("T")[0],
            "month": month,
            "word_count": p.word_count,
            "layout_variant": p.layout_variant,
        })

    archive_years = []
    for y in sorted(years_dict.keys(), reverse=True):
        archive_years.append({
            "year": y,
            "posts": years_dict[y],
            "count": len(years_dict[y]),
        })

    return {
        "stats": {
            "total_posts": total_posts,
            "total_words": total_words,
            "years_span": len(archive_years),
        },
        "years": archive_years,
    }
