# Liquid Editorial · 空间化个人技术博客

> **「杂志级排版 × 空间化交互 × 电影级动效」** 软件开发者个人技术博客系统（Nuxt 4 × FastAPI × SQLite WAL）。

---

## 快速导航

- [系统特性](#系统特性)
- [架构概览](#架构概览)
- [完整路由矩阵](#完整路由矩阵)
- [本地开发快速上手](#本地开发快速上手)
- [种子数据与初始化](#种子数据与初始化)
- [腾讯云 COS 配置](#腾讯云-cos-配置)
- [生产部署](#生产部署)
- [备份与容灾恢复](#备份与容灾恢复)
- [自动化测试](#自动化测试)
- [架构决策与动效规范](#架构决策与动效规范)

---

## 系统特性

1. **杂志级排版 (Liquid Editorial)**：严格瑞士网格、流式字体体系（`clamp()` 计算）、5 种特稿排版模板（`standard`、`wide`、`immersive`、`essay`、`showcase`）、刻度尺式目录索引（`TocScale.vue`）。
2. **空间化交互**：首页无限画布拖拽平移、视差运动、卡片与特稿头图无缝 GSAP Flip 转场。
3. **电影级动效**：开场序幕三位数递增计数、WebGL 液态微形变、文字按行揭示（SplitText）、智能上下文光标（吸附与阅读提示）、磁吸微交互、全屏扩散菜单。
4. **四时光照系统**：晨（薄雾金）、昼（标准米白）、暮（暖橘金）、夜（深邃墨黑）随访客当地时间平滑过渡。
5. **IDE 级代码块**：Shiki 双主题高亮、行号、行高亮、diff 增删标记、聚焦模糊、代码组（Tabs）与终端样式。
6. **自建安全体系**：SQLite WAL 高并发、FTS5 全文搜索与 jieba 中文分词、Argon2id 密码哈希、只存内存的访问令牌 + 每次轮换的 HttpOnly 刷新令牌（重放即吊销会话）、TOTP 两步验证与一次性恢复码、按账号与 IP 的持久化登录限流、会话管理与操作审计、上传按内容识别格式、分层安全响应头与 CSP、蜜罐反垃圾评论。详见 [docs/security.md](docs/security.md)。
7. **全功能独立页面**：成套开源作品集展示、时间河流归档、关于博主（工程元素周期表）、Today I Learned (TIL)、特稿专栏（Series）、工具与装备（/uses）、友链同行（/links）。

---

## 架构概览

```
.
├── apps/
│   ├── web/                     # 前台与后台前端 (Nuxt 4 / Vue 3.5 / UnoCSS / GSAP / Lenis)
│   │   ├── app/
│   │   │   ├── pages/           # 页面体系 (SSR 前台 + CSR 后台 /admin/**)
│   │   │   ├── components/      # 杂志排版、动效与 UI 组件
│   │   │   └── composables/     # Lenis 统一 rAF 动效管线、四时光照、磁吸微交互
│   │   └── server/routes/       # Nitro 服务端路由 (RSS、Atom、JSON Feed、Sitemap、Health)
│   └── api/                     # 后端服务 (Python 3.12+ / FastAPI / SQLAlchemy 2.0 Async / SQLite WAL)
│       ├── app/
│       │   ├── models/          # 21 张数据表模型 (Post, Tag, Series, Project, Comment, TIL, Link...)
│       │   ├── routers/         # 公开 REST API 与管理后台 API
│       │   ├── services/        # 搜索、STS 直传、排版元数据提取
│       │   └── cli.py           # 初始化、种子数据加载、数据库在线热备份与恢复
│       └── tests/               # Pytest 自动化测试套件
├── packages/
│   └── markdown/                # Monorepo 共享 Markdown 渲染引擎 (markdown-it + Shiki)
├── deploy/                      # 生产环境一键部署与 Nginx 反向代理配置
└── docs/                        # 架构决策记录 (ADR) 与动效设计规范
```

---

## 完整路由矩阵

### 公开前台路由
- `/` - 首页无限画布空间
- `/posts` - 杂志目录式文章总索引
- `/posts/:slug` - 特稿详情页（5 种版式模板、刻度尺目录、点赞与分享、评论）
- `/series` - 专栏特辑总览
- `/series/:slug` - 专栏章节流水线
- `/projects` - 开源作品集
- `/projects/:slug` - 开源项目详情与代码卡片
- `/til` - Today I Learned (终端风格微心得与代码切片)
- `/archive` - 时间河流归档（巨幅年份水印与字数统计）
- `/about` - 关于博主（工程元素周期表、纵向履历时间线）
- `/uses` - 工具与装备（硬件、编辑器、终端、字体与 Dotfiles）
- `/links` - 友链与同行（卡片流与友链申请规范）
- `/dev/motion` - 动效验收调试工作台
- `/rss.xml` / `/atom.xml` / `/feed.json` - 全文订阅源
- `/sitemap.xml` / `/robots.txt` - SEO 爬虫支持
- `/api/v1/health` - 后端健康检查 (DB、磁盘、Uptime)
- `/api/health` - Nuxt SSR 进程健康检查

### 管理后台路由 (`/admin/**` 客户端渲染)
- `/admin/login` - 管理员登录（Argon2id 校验）
- `/admin` - 仪表盘总览（指标卡片、特稿状态、访问概览）
- `/admin/posts` - 特稿管理列表（发布、下线、草稿筛选）
- `/admin/posts/new` - 撰写新特稿（分栏实时预览、图片拖拽直传）
- `/admin/posts/:id` - 特稿深度编辑与排版配置
- `/admin/media` - 媒体资产库
- `/admin/til` - Today I Learned 管理
- `/admin/links` - 友链与同行管理
- `/admin/settings` - 站点全域配置
- `/admin/security` - 安全：两步验证、修改密码、登录会话、操作留痕

---

## 本地开发快速上手

### 1. 环境准备
- Node.js ≥ 22.0
- pnpm ≥ 10.0 (`corepack enable`)
- Python ≥ 3.12 与 [uv](https://github.com/astral-sh/uv)

### 2. 安装与构建共享包
```bash
# 安装 Node 依赖 (pnpm workspace)
pnpm install

# 编译共享 Markdown 包
pnpm build:packages
```

### 3. 初始化数据库与种子数据
```bash
# 初始化数据库、生成超级管理员并加载全部种子特稿
uv run --directory apps/api python -m app.cli seed
```
> 演示管理员账号：`admin`，密码：`admin123456`，仅用于本地开发（生产环境拒绝运行 `seed`）。登录后可在「§ 06 安全」修改密码、启用两步验证。

### 4. 启动双端开发服务
打开两个终端：
```bash
# 终端 1: 启动 FastAPI 后端 (:8000)
cd apps/api
uv run fastapi dev app/main.py

# 终端 2: 启动 Nuxt 前端 (:3000)
pnpm dev:web
```

访问 `http://localhost:3000` 即可探索空间化博客；访问 `http://localhost:3000/admin` 进入管理后台。

---

## 腾讯云 COS 配置

生产环境下图片通过 STS 临时密钥从浏览器直传 COS。在根目录 `.env` 中填写：
```env
COS_SECRET_ID=your_cam_secret_id
COS_SECRET_KEY=your_cam_secret_key
COS_REGION=ap-guangzhou
COS_BUCKET=blog-media-1250000000
COS_CDN_DOMAIN=https://img.example.com
COS_STS_DURATION=900
```
> **平滑降级支持 (ADR 002)**：若未配置 COS 秘钥，系统将自动进入本地开发存储模式（媒体保存在 `data/dev_media/`），支持完整的图片拖拽上传与发布。

---

## 生产部署

生产环境采用 Docker Compose 编排：
```bash
# 1. 复制环境变量
cp .env.example .env

# 2. 执行一键部署脚本 (预检 -> 在线备份 -> 构建镜像 -> 迁移 -> 滚动重启 -> 双端健康检查)
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

> 上线前请对照 [docs/security.md](docs/security.md) 第 7 节：`APP_ENV=production` 时，默认或过短的密钥、非 https 的 `SITE_URL` 会让 API 拒绝启动；管理员请用 `python -m app.cli create-admin --username <名字>` 交互创建。

---

## 备份与容灾恢复

### 数据库在线热备份
基于 SQLite 在线备份 API (`sqlite3.backup`)，写操作期间零锁表并生成 gzip 压缩归档：
```bash
uv run --directory apps/api python -m app.cli backup
```
备份产物保存在 `./backups/YYYY-MM-DD/blog.db.gz`。

### 灾难恢复
从指定 gzip 备份解压并原子替换恢复：
```bash
uv run --directory apps/api python -m app.cli restore --from-file backups/2026-10-22/blog.db.gz
```

---

## 自动化测试

```bash
# 1. 后端 API 与业务集成测试 (16 项全绿通过)
uv run --directory apps/api pytest

# 2. 共享 Markdown 引擎测试 (4 项全绿通过)
pnpm --filter @blog/markdown test

# 3. 前端生产构建验证
pnpm --filter @blog/web build
```

---

## 架构决策与动效规范

- [架构决策记录 (ADR 001 - 003)](./docs/decisions.md)
  - ADR 001: 单一 requestAnimationFrame 驱动 Lenis 与 GSAP
  - ADR 002: 存储架构双模式与平滑降级策略
  - ADR 003: SQLite WAL 模式与混合全文搜索设计
- [动效设计与时间轴规范](./docs/motion.md)
  - 缓动曲线 Token、光标物理跟随模型、转场动画协议与弱动效适配
