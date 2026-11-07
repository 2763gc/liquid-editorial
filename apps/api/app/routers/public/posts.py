import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from app.db.session import get_db
from app.models.post import Post, PostTag
from app.models.tag import Tag
from app.schemas.post import PostListItem, PostDetail, CoverOut, SeriesBrief, PostNavBrief, TocItem
from app.schemas.common import PaginationResponse
from app.models.like import PostLike
from app.core.visitor import visitor_hash, RateLimiter

like_limiter = RateLimiter(limit=30, window_seconds=60)
view_limiter = RateLimiter(limit=60, window_seconds=60)
# 浏览去重：同一访客 30 分钟内同一篇只计一次（进程内缓存）
_recent_views: dict[str, float] = {}

router = APIRouter(prefix="/posts", tags=["posts"])

@router.get("", response_model=PaginationResponse[PostListItem])
async def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    tag: str | None = None,
    year: str | None = None,
    featured: bool | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Post)
        .options(selectinload(Post.tags), selectinload(Post.cover))
        .where(Post.status == "published", Post.visibility == "public", Post.deleted_at.is_(None))
    )

    if tag:
        query = query.join(Post.tags).where(Tag.slug == tag)

    if year:
        query = query.where(Post.published_at.startswith(year))

    if featured is not None:
        query = query.where(Post.is_featured == (1 if featured else 0))

    # 统计总数
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # 分页与排序 (置顶优先，发布时间降序)
    query = query.order_by(desc(Post.is_pinned), desc(Post.published_at))
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    posts = result.scalars().all()

    items = []
    for p in posts:
        cover_out = None
        if p.cover:
            cover_out = CoverOut(
                url=p.cover.url,
                width=p.cover.width,
                height=p.cover.height,
                dominant_color=p.cover.dominant_color,
                lqip=p.cover.lqip,
                alt=p.cover.alt,
            )

        items.append(
            PostListItem(
                id=p.id,
                slug=p.slug,
                number=p.number,
                title=p.title,
                subtitle=p.subtitle,
                excerpt=p.excerpt,
                cover=cover_out,
                layout_variant=p.layout_variant,
                accent_color=p.accent_color,
                tags=p.tags,
                word_count=p.word_count,
                reading_minutes=p.reading_minutes,
                view_count=p.view_count,
                like_count=p.like_count,
                is_pinned=bool(p.is_pinned),
                published_at=p.published_at,
            )
        )

    return PaginationResponse(items=items, total=total, page=page, page_size=page_size)

@router.get("/{slug}", response_model=PostDetail)
async def get_post_detail(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    query = (
        select(Post)
        .options(
            selectinload(Post.tags),
            selectinload(Post.cover),
            selectinload(Post.series_rel),
        )
        .where(
            Post.slug == slug,
            Post.deleted_at.is_(None),
            Post.status == "published",
            Post.visibility.in_(("public", "unlisted")),
        )
    )
    result = await db.execute(query)
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="文章不存在")

    liked = (
        await db.scalar(
            select(func.count(PostLike.id)).where(
                PostLike.post_id == post.id, PostLike.visitor_hash == visitor_hash(request)
            )
        )
    ) > 0

    # 解析 TOC
    toc = []
    if post.toc_json:
        try:
            toc = [TocItem(**item) for item in json.loads(post.toc_json)]
        except Exception:
            pass

    # 封面
    cover_out = None
    if post.cover:
        cover_out = CoverOut(
            url=post.cover.url,
            width=post.cover.width,
            height=post.cover.height,
            dominant_color=post.cover.dominant_color,
            lqip=post.cover.lqip,
            alt=post.cover.alt,
        )

    # 专栏
    series_out = None
    if post.series_rel:
        series_out = SeriesBrief(
            slug=post.series_rel.slug,
            title=post.series_rel.title,
            order=post.series_order,
        )

    # 上一篇与下一篇
    prev_query = (
        select(Post.slug, Post.title)
        .where(
            Post.status == "published",
            Post.visibility == "public",
            Post.published_at < (post.published_at or ""),
            Post.deleted_at.is_(None),
        )
        .order_by(desc(Post.published_at))
        .limit(1)
    )
    prev_res = (await db.execute(prev_query)).first()
    prev_brief = PostNavBrief(slug=prev_res[0], title=prev_res[1]) if prev_res else None

    next_query = (
        select(Post.slug, Post.title)
        .where(
            Post.status == "published",
            Post.visibility == "public",
            Post.published_at > (post.published_at or ""),
            Post.deleted_at.is_(None),
        )
        .order_by(Post.published_at.asc())
        .limit(1)
    )
    next_res = (await db.execute(next_query)).first()
    next_brief = PostNavBrief(slug=next_res[0], title=next_res[1]) if next_res else None

    return PostDetail(
        id=post.id,
        slug=post.slug,
        number=post.number,
        title=post.title,
        subtitle=post.subtitle,
        excerpt=post.excerpt,
        content_md=post.content_md,
        toc=toc,
        cover=cover_out,
        layout_variant=post.layout_variant,
        accent_color=post.accent_color,
        tags=post.tags,
        series=series_out,
        word_count=post.word_count,
        reading_minutes=post.reading_minutes,
        view_count=post.view_count,
        like_count=post.like_count,
        liked=liked,
        comment_count=post.comment_count,
        allow_comments=bool(post.allow_comments),
        published_at=post.published_at,
        content_updated_at=post.content_updated_at,
        prev=prev_brief,
        next=next_brief,
    )

@router.post("/{slug}/view")
async def report_post_view(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    import time

    vh = visitor_hash(request)
    view_limiter.check(vh)
    post_id = await db.scalar(
        select(Post.id).where(Post.slug == slug, Post.deleted_at.is_(None), Post.status == "published")
    )
    if not post_id:
        raise HTTPException(status_code=404, detail="文章不存在")

    key = f"{post_id}:{vh}"
    now = time.time()
    counted = False
    if now - _recent_views.get(key, 0) > 1800:
        _recent_views[key] = now
        if len(_recent_views) > 50000:
            for k in [k for k, t in _recent_views.items() if now - t > 1800]:
                _recent_views.pop(k, None)
        await db.execute(update(Post).where(Post.id == post_id).values(view_count=Post.view_count + 1))
        await db.commit()
        counted = True
    view_count = await db.scalar(select(Post.view_count).where(Post.id == post_id))
    return {"slug": slug, "view_count": view_count, "counted": counted}


@router.post("/{slug}/like")
async def like_post(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    vh = visitor_hash(request)
    like_limiter.check(vh)
    post_id = await db.scalar(
        select(Post.id).where(Post.slug == slug, Post.deleted_at.is_(None), Post.status == "published")
    )
    if not post_id:
        raise HTTPException(status_code=404, detail="文章不存在")

    try:
        db.add(PostLike(post_id=post_id, visitor_hash=vh))
        await db.flush()
        await db.execute(update(Post).where(Post.id == post_id).values(like_count=Post.like_count + 1))
        await db.commit()
    except IntegrityError:
        await db.rollback()  # 已经点过赞
    like_count = await db.scalar(select(Post.like_count).where(Post.id == post_id))
    return {"slug": slug, "like_count": like_count, "liked": True}

@router.get("/{slug}/related", response_model=list[PostListItem])
async def get_related_posts(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post).options(selectinload(Post.tags)).where(Post.slug == slug, Post.deleted_at.is_(None))
    )
    post = result.scalar_one_or_none()
    if not post:
        return []

    tag_ids = [t.id for t in post.tags]
    if not tag_ids:
        return []

    related_query = (
        select(Post)
        .options(selectinload(Post.tags), selectinload(Post.cover))
        .join(Post.tags)
        .where(
            Post.id != post.id,
            Tag.id.in_(tag_ids),
            Post.status == "published",
            Post.visibility == "public",
            Post.deleted_at.is_(None),
        )
        .distinct()
        .limit(3)
    )
    related_posts = (await db.execute(related_query)).scalars().all()

    items = []
    for p in related_posts:
        cover_out = None
        if p.cover:
            cover_out = CoverOut(
                url=p.cover.url,
                width=p.cover.width,
                height=p.cover.height,
                dominant_color=p.cover.dominant_color,
                lqip=p.cover.lqip,
                alt=p.cover.alt,
            )
        items.append(
            PostListItem(
                id=p.id,
                slug=p.slug,
                number=p.number,
                title=p.title,
                subtitle=p.subtitle,
                excerpt=p.excerpt,
                cover=cover_out,
                layout_variant=p.layout_variant,
                accent_color=p.accent_color,
                tags=p.tags,
                word_count=p.word_count,
                reading_minutes=p.reading_minutes,
                view_count=p.view_count,
                published_at=p.published_at,
            )
        )
    return items
