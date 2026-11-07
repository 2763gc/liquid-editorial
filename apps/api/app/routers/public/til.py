from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.session import get_db
from app.models.til import TIL

router = APIRouter(prefix="/til", tags=["til"])

@router.get("")
async def list_til(
    tag: str | None = Query(None, description="按标签过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    query = select(TIL)
    count_query = select(func.count(TIL.id))

    if tag:
        query = query.where(TIL.tag == tag)
        count_query = count_query.where(TIL.tag == tag)

    total = await db.scalar(count_query) or 0
    items_res = await db.execute(
        query.order_by(desc(TIL.created_at)).offset((page - 1) * page_size).limit(page_size)
    )
    items = items_res.scalars().all()

    return {
        "items": [
            {
                "id": t.id,
                "title": t.title,
                "tag": t.tag,
                "content_md": t.content_md,
                "created_at": t.created_at.isoformat() if hasattr(t.created_at, "isoformat") else str(t.created_at),
            }
            for t in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 1,
    }

@router.get("/tags")
async def list_til_tags(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(TIL.tag, func.count(TIL.id).label("count"))
        .group_by(TIL.tag)
        .order_by(desc("count"))
    )
    return [{"tag": row[0], "count": row[1]} for row in res.all()]
