import hashlib
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.db.session import get_db
from app.models.comment import Comment
from app.models.post import Post
from app.core.visitor import client_ip, visitor_hash, RateLimiter

comment_limiter = RateLimiter(limit=3, window_seconds=60)
MAX_LINKS = 3

router = APIRouter(prefix="/posts/{slug}/comments", tags=["comments"])

class CommentSubmitRequest(BaseModel):
    author_name: str = Field(..., min_length=1, max_length=50)
    author_email: str | None = None
    author_url: str | None = None
    content_md: str = Field(..., min_length=2, max_length=1000)
    parent_id: int | None = None
    website_trap: str | None = None  # 蜜罐防机器人 (PRD 5.9)

    @field_validator("author_url")
    @classmethod
    def check_url(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip()
        if not re.match(r"^https?://[^\s<>\"']+$", v, re.I):
            raise ValueError("网站地址需以 http:// 或 https:// 开头")
        return v[:300]

    @field_validator("author_email")
    @classmethod
    def check_email(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("邮箱格式不正确")
        return v[:200]

@router.get("")
async def get_post_comments(slug: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        select(Post.id).where(Post.slug == slug, Post.deleted_at.is_(None), Post.status == "published")
    )
    post_id = res.scalar_one_or_none()
    if not post_id:
        raise HTTPException(status_code=404, detail="文章不存在")

    query = (
        select(Comment)
        .where(
            Comment.post_id == post_id,
            Comment.status == "approved",
            Comment.deleted_at.is_(None),
        )
        .order_by(Comment.id.asc())
    )
    comments = (await db.execute(query)).scalars().all()

    # 构建两层树结构 (PRD 5.9)：更深的回复按 root_id 展平，并标注「回复 @某人」
    by_id = {c.id: c for c in comments}
    roots = []
    children_map: dict[int, list] = {}
    for c in comments:
        item = {
            "id": c.id,
            "author_name": c.author_name,
            "avatar_hash": c.avatar_hash,
            "author_url": c.author_url,
            "content_md": c.content_md,
            "is_author": bool(c.is_author),
            "created_at": c.created_at,
            "reply_to": None,
            "replies": [],
        }
        if c.parent_id is None:
            roots.append(item)
            continue
        root_id = c.root_id or c.parent_id
        parent = by_id.get(c.parent_id)
        if parent is not None and parent.parent_id is not None:
            item["reply_to"] = parent.author_name
        children_map.setdefault(root_id, []).append(item)

    for r in roots:
        r["replies"] = children_map.get(r["id"], [])

    return {
        "total": len(comments),
        "items": roots,
    }

@router.post("")
async def submit_comment(
    slug: str,
    req: CommentSubmitRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # 蜜罐拦截：机器人填写了隐藏字段直接返回假成功 (PRD 5.9)
    if req.website_trap:
        return {"status": "pending", "message": "评论已提交审核"}

    comment_limiter.check(visitor_hash(request))

    content = req.content_md.strip()
    if len(re.findall(r"https?://", content)) > MAX_LINKS:
        raise HTTPException(status_code=400, detail="评论中的链接过多")

    res = await db.execute(
        select(Post).where(Post.slug == slug, Post.deleted_at.is_(None), Post.status == "published")
    )
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="文章不存在")
    if not post.allow_comments:
        raise HTTPException(status_code=400, detail="该文章已关闭评论")

    # 校验回复对象属于同一篇文章，并计算所属顶层评论
    root_id = None
    if req.parent_id is not None:
        parent = await db.scalar(
            select(Comment).where(
                Comment.id == req.parent_id,
                Comment.post_id == post.id,
                Comment.deleted_at.is_(None),
            )
        )
        if parent is None:
            raise HTTPException(status_code=400, detail="回复的评论不存在")
        root_id = parent.root_id or parent.id

    # 计算邮箱 Gravatar 哈希
    avatar_hash = None
    if req.author_email:
        clean_email = req.author_email.strip().lower()
        avatar_hash = hashlib.md5(clean_email.encode("utf-8")).hexdigest()

    ip_hash = visitor_hash(request)

    # 创建评论 (默认先审后发状态 pending，或自动通过)
    comment = Comment(
        post_id=post.id,
        parent_id=req.parent_id,
        root_id=root_id,
        author_name=req.author_name.strip(),
        author_email=req.author_email,
        author_url=req.author_url,
        avatar_hash=avatar_hash,
        content_md=content,
        is_author=0,
        # 后台暂无评论审核界面，先即时发布；接入审核后改为 pending（PRD 5.9）
        status="approved",
        ip_hash=ip_hash,
        user_agent=(request.headers.get("user-agent") or "")[:300],
    )
    db.add(comment)
    await db.flush()
    if comment.status == "approved":
        await db.execute(update(Post).where(Post.id == post.id).values(comment_count=Post.comment_count + 1))
    await db.commit()
    await db.refresh(comment)

    return {
        "id": comment.id,
        "author_name": comment.author_name,
        "avatar_hash": comment.avatar_hash,
        "content_md": comment.content_md,
        "status": comment.status,
        "created_at": comment.created_at,
        "message": "评论已发布",
    }
