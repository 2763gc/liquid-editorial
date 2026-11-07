from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from app.db.session import get_db
from app.models.link import FriendLink
from app.models.user import User
from app.core.security import get_current_user

router = APIRouter(prefix="/admin/links", tags=["admin-links"])

class FriendLinkPayload(BaseModel):
    name: str
    url: str
    avatar: str | None = None
    description: str | None = None
    category: str = "tech"
    sort_order: int = 0
    is_active: int = 1

@router.get("")
async def list_links_admin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(FriendLink).order_by(asc(FriendLink.sort_order), asc(FriendLink.id))
    )
    items = res.scalars().all()
    return [
        {
            "id": l.id,
            "name": l.name,
            "url": l.url,
            "avatar": l.avatar,
            "description": l.description,
            "category": l.category,
            "sort_order": l.sort_order,
            "is_active": l.is_active,
        }
        for l in items
    ]

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_link(
    payload: FriendLinkPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    link = FriendLink(
        name=payload.name,
        url=payload.url,
        avatar=payload.avatar,
        description=payload.description,
        category=payload.category,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return {"message": "创建成功", "id": link.id}

@router.put("/{link_id}")
async def update_link(
    link_id: int,
    payload: FriendLinkPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    link = await db.get(FriendLink, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="友链不存在")
    link.name = payload.name
    link.url = payload.url
    link.avatar = payload.avatar
    link.description = payload.description
    link.category = payload.category
    link.sort_order = payload.sort_order
    link.is_active = payload.is_active
    await db.commit()
    return {"message": "更新成功", "id": link.id}

@router.delete("/{link_id}")
async def delete_link(
    link_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    link = await db.get(FriendLink, link_id)
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="友链不存在")
    await db.delete(link)
    await db.commit()
    return {"message": "删除成功"}
