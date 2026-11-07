from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from app.db.session import get_db
from app.models.link import FriendLink

router = APIRouter(prefix="/links", tags=["links"])

@router.get("")
async def list_links(db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(FriendLink)
        .where(FriendLink.is_active == 1)
        .order_by(asc(FriendLink.sort_order), asc(FriendLink.id))
    )
    links = res.scalars().all()
    return [
        {
            "id": l.id,
            "name": l.name,
            "url": l.url,
            "avatar": l.avatar,
            "description": l.description,
            "category": l.category,
        }
        for l in links
    ]
