from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.session import get_db
from app.models.til import TIL
from app.models.user import User
from app.core.security import get_current_user

router = APIRouter(prefix="/admin/til", tags=["admin-til"])

class TILPayload(BaseModel):
    title: str
    tag: str
    content_md: str

@router.get("")
async def list_til_admin(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    total = await db.scalar(select(func.count(TIL.id))) or 0
    res = await db.execute(
        select(TIL).order_by(desc(TIL.created_at)).offset((page - 1) * page_size).limit(page_size)
    )
    items = res.scalars().all()
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
    }

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_til(
    payload: TILPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    til = TIL(
        title=payload.title,
        tag=payload.tag.strip().lower(),
        content_md=payload.content_md,
    )
    db.add(til)
    await db.commit()
    await db.refresh(til)
    return {
        "id": til.id,
        "title": til.title,
        "tag": til.tag,
        "content_md": til.content_md,
        "created_at": til.created_at.isoformat() if hasattr(til.created_at, "isoformat") else str(til.created_at),
    }

@router.put("/{til_id}")
async def update_til(
    til_id: int,
    payload: TILPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    til = await db.get(TIL, til_id)
    if not til:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TIL 不存在")
    til.title = payload.title
    til.tag = payload.tag.strip().lower()
    til.content_md = payload.content_md
    await db.commit()
    return {"message": "更新成功", "id": til.id}

@router.delete("/{til_id}")
async def delete_til(
    til_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    til = await db.get(TIL, til_id)
    if not til:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TIL 不存在")
    await db.delete(til)
    await db.commit()
    return {"message": "删除成功"}
