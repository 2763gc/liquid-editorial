from datetime import datetime, timezone
import hashlib
import re
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.session import get_db
from app.models.media import Media
from app.models.user import User
from app.core.security import get_current_user
from app.services.cos import (
    MAX_UPLOAD_BYTES,
    UploadRejected,
    analyze_image_bytes,
    is_cos_configured,
    issue_upload_credential,
    mime_for_key,
    public_url,
    safe_dev_path,
    sniff_image,
    verify_object_key,
)

router = APIRouter(prefix="/admin/media", tags=["admin-media"])


def reject(e: UploadRejected) -> HTTPException:
    return HTTPException(status_code=e.status, detail=e.message)


def clean_filename(name: str) -> str:
    """只留文件名本身：去掉路径与控制字符"""
    base = re.split(r"[\\/]", name or "")[-1]
    base = "".join(ch for ch in base if ch.isprintable()).strip()
    return base[:200] or "untitled"


class StsRequest(BaseModel):
    filename: str = Field(max_length=255)
    size_bytes: int = Field(ge=1)
    mime_type: str = Field(max_length=64)


class MediaRegisterRequest(BaseModel):
    cos_key: str = Field(max_length=64)
    url: str = Field(max_length=512)
    original_name: str = Field(max_length=255)
    mime_type: str = Field(max_length=64)
    size_bytes: int = Field(ge=1, le=MAX_UPLOAD_BYTES)
    width: int | None = Field(default=None, ge=1, le=100_000)
    height: int | None = Field(default=None, ge=1, le=100_000)
    dominant_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    lqip: str | None = Field(default=None, max_length=8192)
    alt: str | None = Field(default=None, max_length=500)
    caption: str | None = Field(default=None, max_length=1000)


@router.post("/sts")
async def get_upload_credential(
    req: StsRequest,
    user: User = Depends(get_current_user),
):
    """签发上传凭证：对象键由服务端生成，扩展名取自声明的 MIME 而不是文件名"""
    try:
        return issue_upload_credential(req.mime_type, req.size_bytes, user.id)
    except UploadRejected as e:
        raise reject(e)


@router.post("/upload-dev")
async def upload_dev_media(
    file: UploadFile = File(...),
    cos_key: str = Form(..., max_length=64),
    user: User = Depends(get_current_user),
):
    """本地存储模式的直传（ADR 002）：只接受签发给自己的对象键，按内容识别格式，不覆盖已有文件"""
    try:
        dest = safe_dev_path(cos_key)
        if not verify_object_key(cos_key, user.id):
            raise UploadRejected(400, "上传凭证无效，请重新上传")
        if dest.exists():
            raise UploadRejected(409, "该对象已上传过")
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        mime = sniff_image(content)
        if mime != mime_for_key(cos_key):
            raise UploadRejected(415, "文件内容与声明的类型不符")
    except UploadRejected as e:
        raise reject(e)

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(dest, "xb") as f:
            f.write(content)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="该对象已上传过")

    return {
        "cos_key": cos_key,
        # 这条路径总是存在本地目录里，地址固定走 /media-dev
        "url": f"/media-dev/{cos_key}",
        "size_bytes": len(content),
        "mime_type": mime,
        "sha256": hashlib.sha256(content).hexdigest(),
        **analyze_image_bytes(content),
    }


@router.post("")
async def register_media(
    req: MediaRegisterRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    登记媒体。存在本地目录里的文件，尺寸、类型、地址一律从文件本身重新识别，忽略客户端传来的值；
    直传对象存储的文件，地址必须是该对象键对应的公开地址
    """
    if not verify_object_key(req.cos_key, user.id):
        raise HTTPException(status_code=400, detail="上传凭证无效，请重新上传")
    res = await db.execute(select(Media).where(Media.cos_key == req.cos_key))
    existing = res.scalar_one_or_none()
    if existing:
        return existing

    local = safe_dev_path(req.cos_key)
    if local.exists():
        content = local.read_bytes()
        try:
            mime = sniff_image(content)
        except UploadRejected as e:
            raise reject(e)
        meta = analyze_image_bytes(content)
        fields = {
            "url": f"/media-dev/{req.cos_key}",
            "mime_type": mime,
            "size_bytes": len(content),
            "width": meta["width"],
            "height": meta["height"],
            "dominant_color": meta["dominant_color"],
            "lqip": meta["lqip"],
        }
    elif is_cos_configured():
        if req.url != public_url(req.cos_key):
            raise HTTPException(status_code=400, detail="媒体地址与对象键不符")
        if req.mime_type.lower() != mime_for_key(req.cos_key):
            raise HTTPException(status_code=400, detail="媒体类型与对象键不符")
        if req.lqip and not req.lqip.startswith("data:image/webp;base64,"):
            raise HTTPException(status_code=400, detail="非法的占位图")
        fields = {
            "url": req.url,
            "mime_type": mime_for_key(req.cos_key),
            "size_bytes": req.size_bytes,
            "width": req.width,
            "height": req.height,
            "dominant_color": req.dominant_color,
            "lqip": req.lqip,
        }
    else:
        raise HTTPException(status_code=400, detail="文件尚未上传")

    media_obj = Media(
        cos_key=req.cos_key,
        original_name=clean_filename(req.original_name),
        alt=req.alt,
        caption=req.caption,
        **fields,
    )
    db.add(media_obj)
    await db.commit()
    await db.refresh(media_obj)
    return media_obj


@router.get("")
async def list_media(
    page: int = Query(1, ge=1),
    page_size: int = Query(24, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Media).where(Media.deleted_at.is_(None))
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = query.order_by(desc(Media.id)).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@router.delete("/{media_id}")
async def delete_media(
    media_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(Media).where(Media.id == media_id))
    media_obj = res.scalar_one_or_none()
    if not media_obj:
        raise HTTPException(status_code=404, detail="媒体文件不存在")

    media_obj.deleted_at = datetime.now(timezone.utc).isoformat()
    await db.commit()
    return {"message": "媒体已移入回收站"}
