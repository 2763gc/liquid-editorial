# 架构决策记录 (Architecture Decision Records)

本文档记录本项目在实现过程中所做出的关键架构与设计决策（ADR）。

---

## ADR 001: 采用 Monorepo 组织前端、后端与共享渲染器

- **状态**: 已接受
- **日期**: 2026-10-22
- **背景**:
  前台（Nuxt 4 SSR）和管理后台（Nuxt 4 CSR）使用相同的 Vue 技术栈与设计系统，且正文 Markdown 渲染规则（包括 Shiki 代码高亮、GitHub Alerts、Mermaid 等）在前台页面、后台编辑器实时预览、以及评论区渲染中必须保持高度一致。同时后端使用 FastAPI 承载异步数据服务。
- **决策**:
  使用 `pnpm workspace` 组织整体工程：
  - `apps/web`: Nuxt 4 全栈应用（前台 SSR + 后台 CSR）
  - `apps/api`: FastAPI 异步后端
  - `packages/markdown`: 共享 Markdown 渲染器与 Shiki 主题包
  - `deploy/`: 容器化编排与部署脚本
- **影响**:
  前后端代码统一管理，共享包无需独立发布即可实时引用并类型安全，极大降低多端排版不一致风险。

---

## ADR 002: 存储模块开发与生产双模适配（COS + Local Dev Fallback）

- **状态**: 已接受
- **日期**: 2026-10-22
- **背景**:
  PRD 规定生产环境通过 STS 临时密钥从浏览器直传腾讯云 COS。但在本地离线开发、测试和未配置腾讯云密钥的环境下，无法正常调试图片上传与文章配图流程。
- **决策**:
  在 `apps/api/app/services/cos.py` 中抽象存储服务接口，支持双模式：
  1. **生产模式 (Production COS)**: 严格走 STS 临时凭据签发与 COS 直传。
  2. **本地回退模式 (Local Dev)**: 当检测到未填写 `COS_SECRET_ID` 或运行于离线环境时，自动降级为本地媒体服务，通过本地临时上传 API 存入 `data/dev_media` 并通过静态路径提供访问，完全模拟 COS 签名流程。
- **影响**:
  保证了本地开发、测试以及初次安装体验的开箱即用，无需首先开通云端存储桶即可完整演练发布流程。

---

## ADR 003: SQLite WAL 模式与独立定时任务容器进程

- **状态**: 已接受
- **日期**: 2026-10-22
- **背景**:
  数据库选用 SQLite（WAL 模式）。多 worker 的 Web 服务器（如 Gunicorn + 2 Uvicorn workers）若各启动一套 APScheduler，会导致定时发布与统计任务重复执行，同时可能引起锁争用。
- **决策**:
  - SQLite 开启 `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA synchronous=NORMAL;`。
  - 定时调度器由独立的进程或容器运行（`python -m app.jobs.scheduler`），与 API 共享挂载的数据目录，确保任务单实例执行。
