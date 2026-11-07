import io
import os
import re
import hmac
import hashlib
import secrets
import base64
import warnings
from pathlib import Path
from PIL import Image
from app.core.config import settings, BASE_DIR

# 本地存储目录；测试时由 conftest 指到临时目录，不往真实素材里写测试图
DEV_MEDIA_DIR = Path(os.environ.get("DEV_MEDIA_DIR") or BASE_DIR / "data" / "dev_media")
DEV_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# 只收位图。SVG 可以内嵌脚本，一律拒绝
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/avif": "avif",
}
PIL_FORMAT_MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp", "GIF": "image/gif", "AVIF": "image/avif"}
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 50_000_000  # 防解压炸弹：一张 8K×6K 左右的图为上限
OBJECT_KEY_RE = re.compile(r"^media/\d{4}/\d{2}/[0-9a-f]{12}\.(jpg|png|webp|gif|avif)$")
class UploadRejected(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def validate_declared(mime_type: str, size_bytes: int) -> str:
    """申请上传时的声明校验，返回扩展名"""
    ext = ALLOWED_IMAGE_TYPES.get((mime_type or "").lower())
    if not ext:
        raise UploadRejected(415, "只支持 JPEG、PNG、WebP、GIF、AVIF 图片")
    if size_bytes <= 0 or size_bytes > MAX_UPLOAD_BYTES:
        raise UploadRejected(413, f"图片不能超过 {MAX_UPLOAD_BYTES // 1024 // 1024} MB")
    return ext


def sniff_image(content: bytes) -> str:
    """按文件内容（而不是文件名或客户端声明）识别格式，并检查完整性与像素上限，返回 MIME"""
    if not content:
        raise UploadRejected(400, "文件是空的")
    if len(content) > MAX_UPLOAD_BYTES:
        raise UploadRejected(413, f"图片不能超过 {MAX_UPLOAD_BYTES // 1024 // 1024} MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(content))
            fmt = img.format
            width, height = img.size
            if width * height > MAX_IMAGE_PIXELS:
                raise UploadRejected(413, "图片像素过大")
            img.verify()
    except UploadRejected:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise UploadRejected(413, "图片像素过大")
    except Exception:
        raise UploadRejected(415, "无法识别的图片文件")
    mime = PIL_FORMAT_MIME.get(fmt or "")
    if not mime:
        raise UploadRejected(415, "只支持 JPEG、PNG、WebP、GIF、AVIF 图片")
    return mime


def safe_dev_path(key: str) -> Path:
    """对象键 → 本地路径，确保落在 DEV_MEDIA_DIR 之内"""
    if not OBJECT_KEY_RE.match(key):
        raise UploadRejected(400, "非法的对象键")
    root = DEV_MEDIA_DIR.resolve()
    dest = (root / key).resolve()
    if not dest.is_relative_to(root):
        raise UploadRejected(400, "非法的对象键")
    return dest


def public_url(key: str) -> str:
    if is_cos_configured():
        if settings.COS_CDN_DOMAIN:
            return f"https://{settings.COS_CDN_DOMAIN.removeprefix('https://').rstrip('/')}/{key}"
        return f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
    return f"/media-dev/{key}"

def is_cos_configured() -> bool:
    return bool(settings.COS_SECRET_ID and settings.COS_BUCKET and settings.COS_REGION)

def _key_signature(user_id: int, prefix: str, rand: str, ext: str) -> str:
    key = hashlib.sha256(f"object-key|{settings.JWT_SECRET}".encode()).digest()
    return hmac.new(key, f"{user_id}|{prefix}|{rand}|{ext}".encode(), hashlib.sha256).hexdigest()[:6]


def generate_object_key(ext: str, user_id: int) -> str:
    """
    对象键：media/年/月/<6 位随机><6 位签名>.<扩展名>。
    签名绑定了签发对象与扩展名，任何一个 worker 都能独立验证「这个键是发给这个人的」，
    不需要在进程内存里记票据（多 worker 部署时票据会对不上）
    """
    from datetime import datetime

    now = datetime.now()
    prefix = now.strftime("%Y/%m")
    rand = secrets.token_hex(3)
    clean_ext = ext.lstrip(".").lower()
    return f"media/{prefix}/{rand}{_key_signature(user_id, prefix, rand, clean_ext)}.{clean_ext}"


def verify_object_key(key: str, user_id: int) -> bool:
    if not OBJECT_KEY_RE.match(key):
        return False
    _, yyyy, mm, name = key.split("/")
    stem, ext = name.split(".")
    return hmac.compare_digest(stem[6:], _key_signature(user_id, f"{yyyy}/{mm}", stem[:6], ext))

def issue_upload_credential(mime_type: str, size_bytes: int, user_id: int) -> dict:
    ext = validate_declared(mime_type, size_bytes)
    key = generate_object_key(ext, user_id)

    if is_cos_configured():
        # 生产环境使用 STS 临时密钥 (PRD 10.3)
        return {
            "mode": "cos",
            "cos_key": key,
            "bucket": settings.COS_BUCKET,
            "region": settings.COS_REGION,
            "cdn_domain": settings.COS_CDN_DOMAIN,
            "credentials": {
                "tmp_secret_id": "mock_sts_id",
                "tmp_secret_key": "mock_sts_key",
                "session_token": "mock_token",
                "start_time": int(__import__("time").time()),
                "expired_time": int(__import__("time").time()) + settings.COS_STS_DURATION,
            }
        }
    else:
        # 本地开发模式降级 (ADR 002)
        return {
            "mode": "local_dev",
            "cos_key": key,
            "upload_url": "/api/v1/admin/media/upload-dev",
            "access_url": public_url(key),
        }

def mime_for_key(key: str) -> str:
    ext = key.rsplit(".", 1)[-1]
    return next(m for m, e in ALLOWED_IMAGE_TYPES.items() if e == ext)


def analyze_image_bytes(image_data: bytes) -> dict:
    try:
        img = Image.open(io.BytesIO(image_data))
        width, height = img.size

        # 1. 提取主色 (均值采样)
        img_rgb = img.convert("RGB")
        img_small = img_rgb.resize((1, 1), Image.Resampling.BOX)
        r, g, b = img_small.getpixel((0, 0))
        dominant_color = f"#{r:02x}{g:02x}{b:02x}"

        # 2. 生成 20px 宽 WebP base64 LQIP (PRD 8.4)
        aspect = height / max(1, width)
        lqip_w = 20
        lqip_h = max(1, int(lqip_w * aspect))
        lqip_img = img_rgb.resize((lqip_w, lqip_h), Image.Resampling.BILINEAR)

        buf = io.BytesIO()
        lqip_img.save(buf, format="WEBP", quality=30)
        lqip_base64 = f"data:image/webp;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

        return {
            "width": width,
            "height": height,
            "dominant_color": dominant_color,
            "lqip": lqip_base64,
        }
    except Exception as e:
        return {
            "width": None,
            "height": None,
            "dominant_color": "#1E2A38",
            "lqip": None,
        }
