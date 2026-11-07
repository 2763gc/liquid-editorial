from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.session import get_db
from app.models.project import Project

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project)
        .where(Project.deleted_at.is_(None))
        .order_by(desc(Project.is_featured), Project.sort_order.asc(), desc(Project.stars))
    )
    return result.scalars().all()

@router.get("/{slug}")
async def get_project_detail(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Project).where(Project.slug == slug, Project.deleted_at.is_(None))
    )
    proj = result.scalar_one_or_none()
    if not proj:
        raise HTTPException(status_code=404, detail="开源项目不存在")
    return proj
