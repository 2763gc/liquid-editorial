from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.post import Post

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/heatmap")
async def writing_heatmap(days: int = Query(371, ge=7, le=740), db: AsyncSession = Depends(get_db)):
    """写作热力图（PRD 5.6）：最近 N 天里每天的首发与修订篇数，供归档页的点阵使用"""
    res = await db.execute(
        select(Post.published_at, Post.content_updated_at).where(
            Post.status == "published", Post.visibility == "public", Post.deleted_at.is_(None)
        )
    )
    published: Counter[str] = Counter()
    updated: Counter[str] = Counter()
    for pub, upd in res.all():
        if pub:
            published[pub[:10]] += 1
        if upd and (not pub or upd[:10] != pub[:10]):
            updated[upd[:10]] += 1

    end = date.today()
    start = end - timedelta(days=days - 1)
    out = []
    d = start
    while d <= end:
        k = d.isoformat()
        out.append({"date": k, "published": published.get(k, 0), "updated": updated.get(k, 0)})
        d += timedelta(days=1)
    return {"start": start.isoformat(), "end": end.isoformat(), "days": out}
