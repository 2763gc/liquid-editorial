"""
测试库隔离（B25）：pytest 永远不写开发库。
在导入 app 之前把 DATABASE_URL 指向临时目录里的一份在线备份副本，并在副本上建好全部表；
上传目录 DEV_MEDIA_DIR 同样指到临时目录。
"""
import asyncio
import os
import sqlite3
import tempfile
from pathlib import Path

_SRC = Path(__file__).resolve().parents[3] / "data" / "blog.db"
_TMP = Path(tempfile.mkdtemp(prefix="blog-test-")) / "blog.db"
if _SRC.exists():
    src = sqlite3.connect(str(_SRC))
    dst = sqlite3.connect(str(_TMP))
    src.backup(dst)
    dst.close()
    src.close()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TMP.as_posix()}"
# 上传的测试图也落在临时目录（B25：测试不写开发数据）
os.environ["DEV_MEDIA_DIR"] = str(_TMP.parent / "dev_media")

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
import app.models  # noqa: E402,F401


async def _create_all():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.run(_create_all())
