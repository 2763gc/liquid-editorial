import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import event
from app.core.config import settings, BASE_DIR

# 无论何种启动工作目录，始终将相对路径规范化为相对于项目根目录
database_url = settings.DATABASE_URL
if "sqlite" in database_url:
    raw_path = database_url.replace("sqlite+aiosqlite:///", "")
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = (BASE_DIR / db_path).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

engine = create_async_engine(
    database_url,
    echo=(settings.APP_ENV == "development" and False),
    connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
)

# 注册 SQLite WAL 与性能 PRAGMA
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA busy_timeout=5000;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.close()

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
