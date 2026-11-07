import json
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

# 枚举在请求层校验：非法值返回 422，不再撞上数据库 CHECK 约束变成 500（B29）
Layout = Literal["standard", "wide", "immersive", "essay", "showcase"]
Status = Literal["draft", "scheduled", "published", "archived"]
Visibility = Literal["public", "unlisted", "password"]
HexColor = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.post import Post, PostTag
from app.models.tag import Tag
from app.models.user import User
from app.core.security import get_current_user
from app.services.posts import extract_toc, calculate_reading_metrics, slugify

router = APIRouter(prefix="/admin/posts", tags=["admin-posts"])

class CreatePostRequest(BaseModel):
    title: str
    subtitle: str | None = None
    slug: str | None = None
    content_md: str = ""
    layout_variant: Layout = "standard"
    accent_color: str | None = HexColor
    status: Status = "draft"
    visibility: Visibility = "public"
    is_featured: bool = False
    is_pinned: bool = False
    tag_ids: list[int] = []
    cover_media_id: int | None = None

class UpdatePostRequest(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    slug: str | None = None
    content_md: str | None = None
    layout_variant: Layout | None = None
    accent_color: str | None = HexColor
    status: Status | None = None
    visibility: Visibility | None = None
    is_featured: bool | None = None
    is_pinned: bool | None = None
    tag_ids: list[int] | None = None
    cover_media_id: int | None = None

@router.get("")
async def admin_list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = None,
    q: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Post)
        .options(selectinload(Post.tags), selectinload(Post.cover))
        .where(Post.deleted_at.is_(None))
    )

    if status:
        query = query.where(Post.status == status)

    if q:
        query = query.where(Post.title.contains(q))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(desc(Post.id)).offset((page - 1) * page_size).limit(page_size)
    posts = (await db.execute(query)).scalars().all()

    return {
        "items": posts,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.post("")
async def admin_create_post(
    req: CreatePostRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    final_slug = req.slug or slugify(req.title)
    # 保证 slug 唯一
    res = await db.execute(select(Post).where(Post.slug == final_slug))
    if res.scalar_one_or_none():
        final_slug = f"{final_slug}-{int(__import__('time').time())}"

    toc = extract_toc(req.content_md)
    word_count, reading_min, plain_text = calculate_reading_metrics(req.content_md)
    now_iso = datetime.now(timezone.utc).isoformat()

    # 分配最大文章展示编号
    max_num_res = await db.execute(select(func.max(Post.number)))
    max_num = max_num_res.scalar() or 0
    post_number = max_num + 1

    post = Post(
        title=req.title,
        subtitle=req.subtitle,
        slug=final_slug,
        number=post_number,
        excerpt=plain_text[:160] + "..." if plain_text else "",
        content_md=req.content_md,
        content_text=plain_text,
        toc_json=json.dumps(toc, ensure_ascii=False),
        word_count=word_count,
        reading_minutes=reading_min,
        layout_variant=req.layout_variant,
        accent_color=req.accent_color,
        status=req.status,
        visibility=req.visibility,
        is_featured=1 if req.is_featured else 0,
        is_pinned=1 if req.is_pinned else 0,
        cover_media_id=req.cover_media_id,
        published_at=now_iso if req.status == "published" else None,
        content_updated_at=now_iso,
    )

    if req.tag_ids:
        tag_res = await db.execute(select(Tag).where(Tag.id.in_(req.tag_ids)))
        post.tags = list(tag_res.scalars().all())

    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post

@router.get("/{post_id}")
async def admin_get_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Post)
        .options(selectinload(Post.tags), selectinload(Post.cover))
        .where(Post.id == post_id, Post.deleted_at.is_(None))
    )
    res = await db.execute(query)
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="文章不存在")
    return post

@router.patch("/{post_id}")
async def admin_update_post(
    post_id: int,
    req: UpdatePostRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Post)
        .options(selectinload(Post.tags))
        .where(Post.id == post_id, Post.deleted_at.is_(None))
    )
    res = await db.execute(query)
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="文章不存在")

    now_iso = datetime.now(timezone.utc).isoformat()
    if req.title is not None:
        post.title = req.title
    if req.subtitle is not None:
        post.subtitle = req.subtitle
    if req.slug is not None and req.slug != post.slug:
        clash = await db.execute(select(Post.id).where(Post.slug == req.slug, Post.id != post.id))
        if clash.first():
            raise HTTPException(status_code=409, detail="这个 slug 已被另一篇文章使用")
        post.slug = req.slug
    if req.layout_variant is not None:
        post.layout_variant = req.layout_variant
    if req.accent_color is not None:
        post.accent_color = req.accent_color
    if req.visibility is not None:
        post.visibility = req.visibility
    if req.cover_media_id is not None:
        post.cover_media_id = req.cover_media_id
    if req.is_featured is not None:
        post.is_featured = 1 if req.is_featured else 0
    if req.is_pinned is not None:
        post.is_pinned = 1 if req.is_pinned else 0

    if req.status is not None:
        if req.status == "published" and post.status != "published":
            post.published_at = now_iso
        post.status = req.status

    if req.content_md is not None:
        post.content_md = req.content_md
        toc = extract_toc(req.content_md)
        word_count, reading_min, plain_text = calculate_reading_metrics(req.content_md)
        post.toc_json = json.dumps(toc, ensure_ascii=False)
        post.word_count = word_count
        post.reading_minutes = reading_min
        post.content_text = plain_text
        post.excerpt = plain_text[:160] + "..." if plain_text else ""
        post.content_updated_at = now_iso

    if req.tag_ids is not None:
        tag_res = await db.execute(select(Tag).where(Tag.id.in_(req.tag_ids)))
        post.tags = list(tag_res.scalars().all())

    await db.commit()
    await db.refresh(post)
    return post

@router.post("/{post_id}/publish")
async def admin_publish_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Post).where(Post.id == post_id, Post.deleted_at.is_(None)))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="文章不存在")

    post.status = "published"
    post.published_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    return {"message": "文章已发布", "post_id": post.id, "status": post.status}

@router.delete("/{post_id}")
async def admin_delete_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Post).where(Post.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="文章不存在")

    post.deleted_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    return {"message": "文章已软删除移入回收站"}
