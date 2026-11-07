import sys
import argparse
import asyncio
import json
import sqlite3
import gzip
import shutil
from pathlib import Path

# 确保 apps/api 目录始终在 sys.path 中
API_DIR = Path(__file__).resolve().parent.parent
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.core.config import settings, BASE_DIR
from app.db.session import engine, AsyncSessionLocal
from app.db.base import Base
from app.models.tag import Tag
from app.models.media import Media
from app.models.series import Series
from app.models.post import Post, PostTag
from app.models.user import User
from app.models.setting import Setting
from app.models.project import Project
from app.models.comment import Comment
from app.models.til import TIL
from app.models.link import FriendLink
from app.services.posts import extract_toc, calculate_reading_metrics, slugify
from app.core.security import hash_password, password_problems, iso, utcnow
from app.models.security import AdminSession, UserSecurity
from sqlalchemy import update

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables initialized successfully.")

async def _revoke_all_sessions(db, user: User, reason: str) -> None:
    user.token_version += 1
    await db.execute(
        update(AdminSession)
        .where(AdminSession.user_id == user.id, AdminSession.revoked_at.is_(None))
        .values(revoked_at=iso(utcnow()), revoke_reason=reason)
    )

async def create_admin(username: str, password: str, email: str = "admin@example.com"):
    await init_db()
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(User).where(User.username == username))
        existing = res.scalar_one_or_none()
        if existing:
            existing.password_hash = hash_password(password)
            existing.email = email
            existing.failed_login_count = 0
            existing.locked_until = None
            # 重设密码 = 所有已登录的设备全部退出
            await _revoke_all_sessions(db, existing, "password_reset")
            await db.commit()
            print(f"管理员账号 [{username}] 密码已更新，所有会话已退出！")
        else:
            new_user = User(
                username=username,
                password_hash=hash_password(password),
                display_name="Luntrix",
                email=email,
            )
            db.add(new_user)
            await db.commit()
            print(f"管理员账号 [{username}] 创建成功！")

async def reset_mfa(username: str):
    """丢了手机又没有恢复码时的最后一条路：在服务器上停用两步验证，并退出全部会话"""
    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if not user:
            print(f"错误: 账号 [{username}] 不存在")
            sys.exit(1)
        user.totp_secret = None
        sec = await db.get(UserSecurity, user.id)
        if sec:
            sec.totp_pending_secret = None
            sec.totp_enabled_at = None
            sec.totp_last_counter = None
            sec.recovery_codes = None
        await _revoke_all_sessions(db, user, "mfa_reset")
        await db.commit()
        print(f"账号 [{username}] 的两步验证已停用，所有会话已退出。请登录后尽快重新启用。")

def prompt_password(username: str) -> str:
    import getpass

    while True:
        pw = getpass.getpass("新密码（输入不回显）: ")
        problems = password_problems(pw, username)
        if problems:
            print("密码不符合要求：" + "；".join(problems))
            continue
        if getpass.getpass("再输入一次: ") != pw:
            print("两次输入不一致")
            continue
        return pw

def get_raw_db_file() -> Path:
    raw_path = settings.DATABASE_URL.replace("sqlite+aiosqlite:///", "")
    p = Path(raw_path)
    if not p.is_absolute():
        p = (BASE_DIR / p).resolve()
    return p

def backup_database():
    """PRD 12.5: 使用 SQLite 在线备份 API (sqlite3.backup)，杜绝 WAL 损坏"""
    db_file = get_raw_db_file()
    if not db_file.exists():
        print(f"错误: 数据库文件不存在 {db_file}")
        return

    now_str = datetime.now().strftime("%Y-%m-%d")
    backup_dir = BASE_DIR / "backups" / now_str
    backup_dir.mkdir(parents=True, exist_ok=True)

    temp_backup = backup_dir / "temp_backup.db"
    final_gz = backup_dir / "blog.db.gz"

    print(f"开始在线备份数据库: {db_file} -> {final_gz}")
    # 1. 在线热备份保证 WAL 数据完整落盘
    src = sqlite3.connect(str(db_file))
    dest = sqlite3.connect(str(temp_backup))
    with dest:
        src.backup(dest, pages=100)
    dest.close()
    src.close()

    # 2. gzip 压缩
    with open(temp_backup, "rb") as f_in, gzip.open(final_gz, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    if temp_backup.exists():
        temp_backup.unlink()

    print(f"数据库热备份成功！备份文件大小: {final_gz.stat().st_size} 字节，存储于: {final_gz}")

def restore_database(from_file: str):
    """PRD 12.5: 从 gzip 备份恢复数据库"""
    backup_path = Path(from_file)
    if not backup_path.is_absolute():
        backup_path = (BASE_DIR / backup_path).resolve()

    if not backup_path.exists():
        print(f"错误: 指定的备份文件不存在 {backup_path}")
        return

    target_db = get_raw_db_file()
    temp_restored = target_db.parent / "temp_restore.db"

    print(f"解压备份文件: {backup_path} -> 目标: {target_db}")
    with gzip.open(backup_path, "rb") as f_in, open(temp_restored, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

    # 移除原 WAL 和 SHM 文件，确保恢复干净
    for ext in ["", "-wal", "-shm", "-journal"]:
        f = Path(str(target_db) + ext)
        if f.exists():
            f.unlink()

    temp_restored.rename(target_db)
    print("数据库恢复完成！所有特稿与元数据已就绪。")

DEMO_PROJECTS = [
    {
        "name": "liquid-editorial",
        "slug": "liquid-editorial",
        "tagline": "空间化与特稿级开发者博客系统（Nuxt 4 × FastAPI）",
        "language": "TypeScript",
        "language_color": "#3178C6",
        "stars": 1840,
        "forks": 142,
        "repo_url": "https://github.com/luntrix/liquid-editorial",
        "status": "active",
        "is_featured": 1,
        "code_snippet": "const { renderMarkdown } = await import('@blog/markdown');\nexport default defineNuxtConfig({ compatibilityVersion: 4 });",
        "description_md": "## 项目背景\n\n以「杂志级排版 × 空间化交互 × 电影级动效」为核心，为追求极致阅读质感的技术开发者打造。"
    },
    {
        "name": "rust-mini-executor",
        "slug": "rust-mini-executor",
        "tagline": "基于 epoll 与 Waker 的单线程与 Work-Stealing 异步协程运行时",
        "language": "Rust",
        "language_color": "#DEA584",
        "stars": 820,
        "forks": 65,
        "repo_url": "https://github.com/luntrix/rust-mini-executor",
        "status": "active",
        "is_featured": 1,
        "code_snippet": "pub fn block_on<F: Future>(future: F) -> F::Output {\n    let mut executor = Executor::new();\n    executor.run(future)\n}",
        "description_md": "从零实现的 Rust 异步运行时教学与生产参考项目。"
    },
    {
        "name": "lsm-kv-engine",
        "slug": "lsm-kv-engine",
        "tagline": "采用跳表与 SSTable 分层压实的轻量级嵌入式持久化存储引擎",
        "language": "Python",
        "language_color": "#3572A5",
        "stars": 450,
        "forks": 38,
        "repo_url": "https://github.com/luntrix/lsm-kv-engine",
        "status": "maintained",
        "is_featured": 1,
        "code_snippet": "class LSMTree:\n    def put(self, key: bytes, val: bytes) -> None:\n        self.memtable.insert(key, val)",
        "description_md": "LSM-Tree 算法精简实现，附带完整的恢复与压实测试用例。"
    },
    {
        "name": "tres-fluid-shaders",
        "slug": "tres-fluid-shaders",
        "tagline": "Vue 3 & Three.js 声明式液态噪点位移与 RGB 分离着色器库",
        "language": "GLSL",
        "language_color": "#5686A5",
        "stars": 630,
        "forks": 49,
        "repo_url": "https://github.com/luntrix/tres-fluid-shaders",
        "status": "active",
        "is_featured": 1,
        "code_snippet": "uniform float uTime;\nvarying vec2 vUv;\nvoid main() {\n  vec2 uv = vUv + sin(uTime * 2.0) * 0.02;\n  gl_FragColor = texture2D(uTexture, uv);\n}",
        "description_md": "电影级动态着色器集合，支持鼠标交互感应。"
    },
    {
        "name": "sqlite-wal-pool",
        "slug": "sqlite-wal-pool",
        "tagline": "针对 WAL 模式的高性能并发连接池与只读副本调度器",
        "language": "Go",
        "language_color": "#00ADD8",
        "stars": 390,
        "forks": 27,
        "repo_url": "https://github.com/luntrix/sqlite-wal-pool",
        "status": "active",
        "is_featured": 0,
        "code_snippet": "type Pool struct {\n    writer *sql.DB\n    readers []*sql.DB\n}",
        "description_md": "解决多工作进程 SQLite 锁竞争的高并发调度中间件。"
    },
    {
        "name": "typst-editorial-press",
        "slug": "typst-editorial-press",
        "tagline": "现代排版语言 Typst 印刷特稿杂志模板系统",
        "language": "Typst",
        "language_color": "#239DAD",
        "stars": 280,
        "forks": 19,
        "repo_url": "https://github.com/luntrix/typst-editorial-press",
        "status": "maintained",
        "is_featured": 0,
        "code_snippet": "#let editorial-page(title, body) = {\n  set page(paper: \"a4\", margin: 2.5cm)\n  show heading: it => text(font: \"Noto Serif SC\", it)\n  body\n}",
        "description_md": "专为技术论文与季刊设计的排版模板。"
    }
]

DEMO_SERIES = [
    {
        "slug": "systems-craft",
        "title": "现代系统编程之道",
        "description": "深入理解内存模型、异步运行时设计与高并发存储引擎内核实现。",
        "status": "ongoing",
        "sort_order": 1,
    },
    {
        "slug": "liquid-design",
        "title": "特稿级排版设计模式",
        "description": "探索 Web 空间化交互、杂志印刷排版质感与电影级动效的工程实践。",
        "status": "completed",
        "sort_order": 2,
    },
]

DEMO_TIL = [
    {
        "title": "Rust 2024 Edition 中 async fn in trait 的生命周期推导规则",
        "tag": "rust",
        "content_md": "在 Rust 2024 中，Trait 声明中的 `async fn` 默认隐式捕获所有输入参数的生命周期。\n\n```rust\ntrait Fetcher {\n    // 编译器自动展开为: impl Future<Output = String> + use<'a, Self>\n    async fn fetch<'a>(&'a self, key: &'a str) -> String;\n}\n```\n当需要显式切断生命周期关联时，可以使用 `+ use<..>` 精确捕获声明。",
    },
    {
        "title": "Vue 3.5 useId() 原理与 SSR 确定性水合",
        "tag": "vue",
        "content_md": "Vue 3.5 引入了原生 `useId()` composable。它基于 App 根级计数器为每个组件生成确定性的唯一前缀，完美避免客户端与服务端水合时的 ID 不一致：\n\n```ts\nconst id = useId()\n// 服务端与客户端水合一致: 'v-0', 'v-1'\n```",
    },
    {
        "title": "SQLite WAL 模式下的 checkpoint 机制与高并发读取优化",
        "tag": "sqlite",
        "content_md": "开启 WAL (Write-Ahead Logging) 模式后，读者读操作完全不阻塞写操作。但 WAL 文件过大会影响读取性能，定期触发 PASSIVE 或 RESTART checkpoint 能将日志刷回主文件：\n\n```sql\nPRAGMA journal_mode = WAL;\nPRAGMA wal_autocheckpoint = 1000;\n```",
    },
    {
        "title": "CSS :has() 选择器与流体网格适配",
        "tag": "css",
        "content_md": "使用 `:has()` 可以在父元素层级感知子元素的结构与形态，彻底摆脱过去的 JS 布局注入：\n\n```css\n.article-grid:has(.featured-cover) {\n  grid-template-columns: 2fr 1fr;\n}\n```",
    },
    {
        "title": "Python 3.12+ PEP 695 泛型形参新语法",
        "tag": "python",
        "content_md": "Python 3.12 不再需要手动从 `typing` 模块导入 `TypeVar`：\n\n```python\ntype Coordinate[T: (int, float)] = tuple[T, T]\n\ndef identity[T](val: T) -> T:\n    return val\n```\n类型形参在作用域内自动惰性求值，清晰简洁。",
    },
    {
        "title": "Git worktree 打造零开销多分支并行工作流",
        "tag": "git",
        "content_md": "无需 `git stash` 频繁切换分支，直接开辟新工作树：\n\n```bash\ngit worktree add ../hotfix-branch hotfix\ncd ../hotfix-branch\n# 独立工作树，零冲突切换\n```",
    },
]

DEMO_LINKS = [
    {
        "name": "Dan Abramov",
        "url": "https://overreacted.io",
        "avatar": "https://api.dicebear.com/7.x/identicon/svg?seed=Dan",
        "description": "深入浅出探讨 React 与编程心理模型的作者随笔",
        "category": "tech",
        "sort_order": 1,
    },
    {
        "name": "Evan You",
        "url": "https://evanyou.me",
        "avatar": "https://api.dicebear.com/7.x/identicon/svg?seed=Evan",
        "description": "Vue.js & Vite 创造者，关于开源架构与独立创收的思考",
        "category": "tech",
        "sort_order": 2,
    },
    {
        "name": "Anthony Fu",
        "url": "https://antfu.me",
        "avatar": "https://api.dicebear.com/7.x/identicon/svg?seed=Anthony",
        "description": "狂热的开源狂想家，Vite / UnoCSS / Nuxt 核心贡献者",
        "category": "tech",
        "sort_order": 3,
    },
    {
        "name": "Rust Magazine",
        "url": "https://rustmagazine.github.io",
        "avatar": "https://api.dicebear.com/7.x/identicon/svg?seed=RustMag",
        "description": "专注于 Rust 生产实践、内存模型与系统编程深度特刊",
        "category": "inspiration",
        "sort_order": 4,
    },
    {
        "name": "Overleaf Editorial",
        "url": "https://www.overleaf.com/blog",
        "avatar": "https://api.dicebear.com/7.x/identicon/svg?seed=Overleaf",
        "description": "学术论文、协作式 LaTeX 排版与设计思考",
        "category": "inspiration",
        "sort_order": 5,
    },
]

async def seed_data():
    if settings.is_production:
        print("错误: 生产环境不允许写入演示数据（其中包含演示账号 admin / admin123456）")
        sys.exit(1)
    await init_db()
    await create_admin("admin", "admin123456", "admin@example.com")
    print("开始写入演示种子数据...")
    async with AsyncSessionLocal() as db:
        # 1. 开源项目
        for p in DEMO_PROJECTS:
            res = await db.execute(select(Project).where(Project.slug == p["slug"]))
            if not res.scalar_one_or_none():
                db.add(Project(
                    name=p["name"],
                    slug=p["slug"],
                    tagline=p["tagline"],
                    language=p["language"],
                    language_color=p["language_color"],
                    stars=p["stars"],
                    forks=p["forks"],
                    repo_url=p["repo_url"],
                    status=p["status"],
                    is_featured=p["is_featured"],
                    code_snippet=p["code_snippet"],
                    description_md=p["description_md"],
                ))

        # 2. 专栏
        for s in DEMO_SERIES:
            res = await db.execute(select(Series).where(Series.slug == s["slug"]))
            if not res.scalar_one_or_none():
                db.add(Series(
                    slug=s["slug"],
                    title=s["title"],
                    description=s["description"],
                    status=s["status"],
                    sort_order=s["sort_order"],
                ))

        # 3. TIL 今日所学
        for t in DEMO_TIL:
            res = await db.execute(select(TIL).where(TIL.title == t["title"]))
            if not res.scalar_one_or_none():
                db.add(TIL(
                    title=t["title"],
                    tag=t["tag"],
                    content_md=t["content_md"],
                ))

        # 4. 友链
        for l in DEMO_LINKS:
            res = await db.execute(select(FriendLink).where(FriendLink.url == l["url"]))
            if not res.scalar_one_or_none():
                db.add(FriendLink(
                    name=l["name"],
                    url=l["url"],
                    avatar=l["avatar"],
                    description=l["description"],
                    category=l["category"],
                    sort_order=l["sort_order"],
                ))

        await db.commit()

        # 5. 关联部分已发布文章到专栏
        series_res = await db.execute(select(Series))
        all_series = series_res.scalars().all()
        series_map = {s.slug: s.id for s in all_series}

        posts_res = await db.execute(select(Post))
        all_posts = posts_res.scalars().all()
        for idx, post in enumerate(all_posts):
            if "rust" in post.slug or "executor" in post.slug:
                post.series_id = series_map.get("systems-craft")
                post.series_order = idx + 1
            elif "fluid" in post.slug or "layout" in post.slug or "visual" in post.slug:
                post.series_id = series_map.get("liquid-design")
                post.series_order = idx + 1
        await db.commit()

    print("开源项目、专栏、TIL 与友链种子数据已全部写入！")

def main():
    parser = argparse.ArgumentParser(description="Liquid Editorial CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init-db", help="Initialize database tables")
    admin_parser = subparsers.add_parser("create-admin", help="Create an administrator account")
    admin_parser.add_argument("--username", default="admin")
    admin_parser.add_argument("--password", default=None, help="不填则交互输入（推荐，避免密码留在 shell 历史里）")
    admin_parser.add_argument("--email", default="admin@example.com")
    mfa_parser = subparsers.add_parser("reset-mfa", help="Disable two-factor auth for an account and sign out all sessions")
    mfa_parser.add_argument("--username", default="admin")
    subparsers.add_parser("seed", help="Load seed demo data")

    subparsers.add_parser("backup", help="Perform online SQLite backup with gzip")
    restore_parser = subparsers.add_parser("restore", help="Restore database from gzip backup")
    restore_parser.add_argument("--from-file", required=True, dest="from_file", help="Path to backup .gz file")

    args = parser.parse_args()

    if args.command == "init-db":
        asyncio.run(init_db())
    elif args.command == "create-admin":
        password = args.password or prompt_password(args.username)
        problems = password_problems(password, args.username)
        if problems:
            if settings.is_production:
                print("错误: 密码不符合要求：" + "；".join(problems))
                sys.exit(1)
            print("警告: 密码强度不足（" + "；".join(problems) + "），仅限开发环境使用")
        asyncio.run(create_admin(args.username, password, args.email))
    elif args.command == "reset-mfa":
        asyncio.run(reset_mfa(args.username))
    elif args.command == "seed":
        asyncio.run(seed_data())
    elif args.command == "backup":
        backup_database()
    elif args.command == "restore":
        restore_database(args.from_file)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
