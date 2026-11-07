from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.series import Series
from app.models.post import Post

router = APIRouter(prefix="/series", tags=["series"])

@router.get("")
async def list_series(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Series)
        .order_by(Series.sort_order.asc(), Series.id.desc())
    )
    series_list = res.scalars().all()
    results = []

    for s in series_list:
        # 统计该专栏下已发布文章数与总字数
        stat_res = await db.execute(
            select(
                func.count(Post.id),
                func.coalesce(func.sum(Post.word_count), 0),
            ).where(
                Post.series_id == s.id,
                Post.status == "published",
                Post.visibility == "public",
                Post.deleted_at.is_(None),
            )
        )
        post_count, total_words = stat_res.one()

        results.append({
            "id": s.id,
            "slug": s.slug,
            "title": s.title,
            "description": s.description,
            "status": s.status,
            "post_count": post_count,
            "total_words": total_words,
        })

    return results

@router.get("/{slug}")
async def get_series_detail(slug: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Series).where(Series.slug == slug)
    )
    series = res.scalar_one_or_none()
    if not series:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="专栏不存在")

    # 查询该专栏下的已发布文章，按 series_order 升序排列
    posts_res = await db.execute(
        select(Post)
        # 软删除与不公开的文章不能出现在专栏里（B41）
        .where(
            Post.series_id == series.id,
            Post.status == "published",
            Post.visibility == "public",
            Post.deleted_at.is_(None),
        )
        .order_by(asc(Post.series_order), asc(Post.published_at))
    )
    posts = posts_res.scalars().all()

    total_words = sum(p.word_count for p in posts)
    total_reading_time = sum(p.reading_minutes for p in posts)

    return {
        "id": series.id,
        "slug": series.slug,
        "title": series.title,
        "description": series.description,
        "status": series.status,
        "post_count": len(posts),
        "total_words": total_words,
        "total_reading_time": total_reading_time,
        "posts": [
            {
                "id": p.id,
                "slug": p.slug,
                "title": p.title,
                "subtitle": p.subtitle,
                "excerpt": p.excerpt,
                "series_order": p.series_order,
                "reading_minutes": p.reading_minutes,
                "number": p.number,
                "accent_color": p.accent_color,
                "published_at": (
                    p.published_at.isoformat()
                    if hasattr(p.published_at, "isoformat")
                    else str(p.published_at)
                ) if p.published_at else None,
            }
            for p in posts
        ]
    }
