# 阶段 0 审计报告：复核与补充审计

> 日期：2026-10-22 · 范围：PRD 全文 + 整个代码库 · 本阶段只读，未修改任何业务代码
> 产出：本文件、`docs/audit/screenshots/before/`（60 张截图 + `layout-report.json`）

---

## 0. 结论摘要

1. **工作区不是干净的 HEAD。** `master` 上有 24 个已修改文件和 7 个未跟踪文件，约 +4400 / −1500 行，未提交。从内容看，这是上一轮已经开始的修复（服务端渲染 Markdown、新画布、主题内联脚本、Lenis 插件、评论限流、点赞表等）。
   - 本报告对每条问题**同时给出 HEAD（`fe66245`）和当前工作区（下称 WIP）的状态**：HEAD 的状态靠读代码核实，WIP 的状态靠实际运行核实。
   - 是否把 WIP 作为后续基线，需要你决定（见第 9 节 D1）。
2. **B01–B23 在 HEAD 上全部复现**（B01 有一处与描述不符：只有 1 篇文章没有坐标，其余都有）。WIP 已修复其中 **6 条**，**15 条只修了一部分**，**2 条未动**。WIP 也带来了新问题，例如 hydration 不一致，以及画布卡片相互重叠。
3. **新发现 26 条问题（B24–B49），其中 P0 有 9 条**。最严重的几条：
   - 测试直接写入开发库，一篇测试文章被公开发布。
   - 禁用 JS 时开场遮罩永久盖住页面。
   - 没有任何 Alembic 迁移。
   - 后台多个接口返回 500。
   - 开发用上传接口可以路径穿越。
   - COS STS 是假实现。
   - `pnpm dev:api` 无法启动。
4. **性能基线（WIP 生产构建）：**
   - 移动端 Lighthouse：首页 55、文章页 56。
   - 首页首屏 JS 253 KB（gzip），超出 180 KB 预算。
   - 项目详情页首屏 JS 680 KB（gzip），因为 Shiki 和 oniguruma wasm 仍然打进了浏览器包。
   - 拖拽和滚动在本机不限速时没有掉帧。CPU 4 倍降速后，页面转场出现 46 个长任务，最长 876 ms。
5. **PRD 完成度很低。** 第 4、5、6、9、10 节共列出 79 项功能：
   - 已完成：7 项
   - 部分完成：47 项
   - 缺失：16 项
   - 与 PRD 不符：6 项
   - 缺失与部分完成混合：2 项
   - 签名动效 14 项中，只有 M6 完整实现。
   - 主要缺口在后台（编辑器、评论审核、项目、标签、专栏、独立页面）、签名动效（M2、M3、M9 等）、定时任务和 COS 直传。

---

## 1. 审计对象、环境与方法

| 项目 | 内容 |
| --- | --- |
| 代码版本 | HEAD `fe66245` + 未提交 WIP（见 `git status`） |
| 运行环境 | Windows 11，Node 24.16，pnpm 12.14，uv 0.12.3，Nuxt 3.21.11（compat v4），Vite 7.3，Vue 3.5.44，Chrome 稳定版 |
| 前端 | `pnpm dev:web` 用于功能与 hydration 检查；`nuxt build` 生产构建（`node .output/server/index.mjs`）用于性能与截图 |
| 后端 | `pnpm dev:api` 启动失败（见 B24），改用 `uv run uvicorn app.main:app --port 8000`。破坏性测试（建草稿、发评论、限流）在 **8001 端口的数据库副本**上进行 |
| 浏览器自动化 | 无头 Chrome + puppeteer-core 24 + Lighthouse 12（安装在会话临时目录，未写入仓库）。内置浏览器面板处于隐藏状态时 rAF 会被节流，因此没有用它做测量 |
| 帧率口径 | 页面内 rAF 时间戳加 `longtask` PerformanceObserver。分 1 倍 CPU 和 4 倍 CPU 降速两组（4 倍用来近似中端移动设备）。本机显示刷新率约 120 Hz，所以 1 倍组的平均帧率上限约 120 |
| Lighthouse 口径 | 移动端默认模拟（Slow 4G + 4 倍 CPU）。服务器是没有开启压缩的 Nitro Node 服务，生产环境由 Nginx 负责 Brotli 压缩，所以传输体积偏大。Google Fonts 走公网 |

### 1.1 审计过程对数据的影响（如实说明）

- **启动 WIP 后端时 `create_all` 在 `data/blog.db` 中新建了 `post_likes` 表**（只增不改）。审计开始前，我已经用 SQLite 在线备份 API 把原库快照到会话临时目录的 `scratchpad/db/baseline.db`。
- **对真实库的计数器写入：**
  - 浏览器测试在 8000 端口进行，给文章 2 点了一次赞（`like_count` 41→42，并写入 1 条 `post_likes` 记录）。
  - 爬取过程让若干文章的 `view_count` 增加了。
  - 没有删除或改写任何内容数据。
- **`backups/2026-10-22/blog.db.gz` 被覆盖。** 现有 pytest 的 `test_backup` 会写入仓库的 `backups/<日期>/blog.db.gz`，把 13:48 的旧备份换成了一份审计开始时的数据快照（这本身也暴露了 B25）。
- 如需回滚上述计数器，可以用 `baseline.db` 还原，见第 9 节 D7。

---

## 2. 启动与运行时错误

| # | 场景 | 现象 | 关联 |
| --- | --- | --- | --- |
| R1 | `pnpm dev:api` | `RuntimeError: To use the fastapi command, please install "fastapi[standard]"`，进程退出 | B24 |
| R2 | 任意前台页面，`localStorage.blog_theme` 为 `light` 或 `dark`，或者当前时段不是「昼」（WIP） | `[Vue warn]: Hydration text content mismatch … rendered on server: 自动 · 昼 – expected on client: 夜`，随后报 `Hydration completed but contains mismatches.`（error），并有一条 attribute mismatch（`title`）。**所有 16 个前台页面都会出现** | B27 |
| R3 | `/search?q=…`、`/now` | 页面 404；SSR 与客户端都报 `[Vue Router warn]: No match found for location with path "/search"` | B20 |
| R4 | HEAD：页脚 RSS 使用 `NuxtLink` | `No match found for location with path "/rss.xml"`（WIP 已改为 `<a>`） | B16 |
| R5 | HEAD：开场动画 | `GSAP target null not found`（WIP 未复现，并且关闭了 `nullTargetWarn`，可能把其他问题一起掩盖） | B12 |
| R6 | `pnpm test`（根目录） | `apps/web` 没有任何测试文件，vitest 以 “No test files found” 退出 1 | B45 |
| R7 | `pnpm lint` | `apps/web` 没有 ESLint 配置 | B45 |
| R8 | `nuxi typecheck` | `Cannot find matching tsconfig.json in apps/web` | B45 |
| R9 | `pytest`（WIP，用数据库副本） | 14 通过、2 失败：`no such table: post_likes`（ASGITransport 不触发 lifespan，没有迁移就没有新表）；`test_backup` 的路径断言写死了 | B25、B28 |
| R10 | 后台接口 | `POST /admin/posts` 传入非法 status、`PATCH` 改出重复 slug、`DELETE /admin/media/{id}` 都返回 **500**，响应体是纯文本 `Internal Server Error`，不是统一错误格式 | B29 |
| R11 | 网络 4xx（公开接口） | `/canvas`、`/tils`、`/stats/heatmap`、`/pages/{slug}`、`/likes`、`/sitemap` 都返回 404 | B20 |

> 在默认时段（昼）、默认主题（自动）下，16 个前台页面在开发模式下的控制台**零错误、零警告**。404 页面的错误只来自预期的 404 响应。

---

## 3. B01–B23 复核

状态说明：✅ 已修复 · ◐ 部分修复 · ❌ 未修复 · ⚠ 修复后带来新问题。

| 编号 | HEAD 复核 | WIP 状态 | 证据与说明 |
| --- | --- | --- | --- |
| B01 | 确认（有一处不符） | ◐ | 列表接口确实没有返回 `canvas_x/y`。但数据库**并非全是空值**：种子文章 1–12 有坐标，只有测试文章 13 为空。WIP 改为前端用固定种子自动布局，完全忽略数据库坐标；后端仍然没有 `/canvas` 接口，也没有返回坐标 |
| B02 | 确认 | ◐ ⚠ | HEAD 实测与描述一致：`panX = ref(0)`、`transition-all duration-300`、`hover:shadow-xl`、逐帧 `backgroundPosition`、独立 rAF。WIP 已改为普通变量 + `gsap.ticker` + transform。**新问题：**卡片内层仍有 `box-shadow` 过渡（PRD 2.5 禁止阴影），而且见 B37 |
| B03 | 确认 | ◐ ⚠ | WIP 已支持 Pointer Events；拖动超过 6px 会拦截点击（实测拖完松手不跳转）；取模循环和全屏首屏也已实现。**未完成：**纵向滚轮不平移画布，筛选只是变淡而不是 Flip 重排，触屏切到列表视图有闪烁。新问题见 B37、B38 |
| B04 | 确认（toc_json 里是 `lsmtree-he-xin-zu-jian`，文本为「LSMTree 核心组件」） | ✅ | WIP 由渲染器生成 id 和目录，并保留中文。实测：3 个目录锚点都能找到对应元素，点击后滚动到位，hash 正确。**遗留：**后端 `extract_toc` 和 `toc_json` 字段仍是旧算法，已没人使用，应删除或统一 |
| B05 | 确认 | ◐ | 文章页已改由 Nitro 渲染（`/api/content/posts/[slug]`）。但 `projects/[slug].vue` 和后台编辑器仍然在客户端调用 `renderMarkdown`，生产包里还有 Shiki 核心（94 KB gz）、oniguruma wasm（225 KB gz）和 470 个语法/主题分包（共 2.5 MB gz）。**首页会预取 Shiki 分块**（画布上的项目卡片链接触发 NuxtLink prefetch）。缓存只有内存 Map，没有 SWR |
| B06 | 确认（`text: str`、逐个读 `offsetTop`） | ✅ | WIP 改用 IntersectionObserver。实测在 1440 下 sticky 生效（top 96px）。≤1024px 时侧栏隐藏，只剩 `<details>` 目录 |
| B07 | 确认 | ◐ | 进度条已改用 `scaleX`；点赞已落库并去重（实测刷新后计数和按下状态都保留）；浏览量 30 分钟去重。**未完成：**去重记录在进程内存里，重启后丢失，多个 worker 之间也不共享；点赞失败时不回滚、不提示；接口是 `/posts/{slug}/like`，不是 PRD 的 `POST /likes`；新表没有迁移（B28） |
| B08 | 确认 | ◐ | WIP 已有代码块头部、语言标签、文件名、复制按钮、超过 30 行折叠；Shiki 双主题使用 CSS 变量。**未完成：**行号、`code-group`、自动换行开关、横向溢出渐隐、文件类型图标；终端块每行之间多出一个空行（B43） |
| B09 | 确认（没有加载任何字体，`font-serif` 落到 Georgia） | ◐ | WIP 通过 Google Fonts 加载了 Fraunces、Inter、JetBrains Mono 和 Noto Serif SC，UnoCSS 已映射到变量。但 Google Fonts 在国内不可用，而且**阻塞渲染约 2.3 s**（Lighthouse），CSS 有 122 KB；Noto Sans SC 没有加载，界面中文落到微软雅黑；没有 cn-font-split，也没有托管到 COS |
| B10 | 确认 | ✅ | WIP 已删除 `scroll-behavior: smooth`，全站只有一个 Lenis，由 `gsap.ticker` 驱动并同步 ScrollTrigger，页面不可见时 ticker 休眠，路由切换后 resize 并 refresh |
| B11 | 确认（只有暗色覆盖，主题在 onMounted 写入） | ◐ ⚠ | WIP 已加 `<head>` 内联脚本；`[data-theme=light][data-period]` 覆盖实测有效（22 点选「昼」时背景为 #F2EFE8）；T 键可以循环到「自动」。**未修复：**通过客户端路由「前台 → 后台 → 前台」后，主题仍是 dark（实测中午 `mode=auto, theme=dark`）。**新问题：**hydration 不一致（B27） |
| B12 | 确认 | ◐ | WIP 改为 SSR 输出遮罩，`curtain-seen` 类在首屏渲染前写入，已无 null target。**新问题：**禁用 JS 时遮罩永久覆盖页面（B26）。开发模式下从导航开始到遮罩移除共 2.48 s（含水合时间），时间线本身是 1.6 s，需要在生产环境复测 |
| B13 | 确认 | ✅ | WIP 用 quickTo 写 transform、用 scale 表示尺寸变化；隐藏系统光标，输入框保留文本光标；触屏和减弱动效模式下不渲染 |
| B14 | 确认 | ◐ | WIP 改为 clip-path 圆形扩散，并通过 lockScroll 停止 Lenis（实测打开后滚动距离为 0）。**未完成：**悬停时没有页面预览图跟随光标；动画进行中会忽略新的点击，不能被打断（PRD 3.1-4） |
| B15 | 确认 | ◐ | WIP 只监听元素自身事件，进入时缓存一次位置。但只在元素边界内生效，PRD 要求「距离 80px 内」；复位用 `elastic.out`，不是 PRD 的 Token |
| B16 | 确认 | ✅ | 实测：向下滚动后顶栏 `top=-64`，向上滚动后回到 0；RSS 链接已改为 `<a>` |
| B17 | 确认 | ✅ | WIP 实测草稿返回 404，草稿的评论接口也返回 404 |
| B18 | 确认 | ◐ | WIP 实测：`javascript:` 地址返回 422；链接超过 3 个返回 400；跨文章 parent_id 返回 400；三级回复被展平到根评论下，并带 `reply_to`；计数原子更新；蜜罐已绑定。**未修复：**限流按 IP+UA 计算，**换一个 UA 就能绕过**（实测 4/4 条通过）；状态固定为 approved（PRD 要求先审后发）；没有敏感词过滤 |
| B19 | 确认 | ◐ | WIP 改为内存全量打分，三次结果一致。**新问题：**按子串匹配会误命中，例如搜 `useState` 返回 3 篇，但库里没有任何一篇包含它（被拆成 use/state 后匹配到 user、because）；单个汉字也计分，搜「运行时」返回 7 篇；单独搜 `gather` 找不到 `asyncio.gather`；没有用 FTS5 / bm25；只能搜文章 |
| B20 | 确认 | ❌ | `/search` 页面 404，`/canvas`、`/tils`、`/stats/heatmap`、`/pages/{slug}`、`/likes`、`/sitemap` 接口都是 404；后台没有评论审核、项目、标签与专栏、独立页面管理 |
| B21 | 确认（HEAD 用 `alert()`，并原样输出 `{{ c.content_md }}`） | ◐ | WIP 用内联 notice 代替 `alert()`，按 `status` 区分提示，提交失败会显示错误。但评论用的是前端正则版 Markdown（`renderLite`），不是 PRD 要求的共享渲染器受限模式，代码块没有高亮；待审核评论对提交者本人不可见；后台仍有 6 处 `alert`/`confirm` |
| B22 | 确认 | ❌ | 年份写死为 2026/2025/2024，选 2025 后列表为 0 行；浏览器后退后 URL 变回空，但按钮状态没有同步 |
| B23 | 确认 | ◐ | WIP 在首页、文章页和全局样式上做了编辑部风格的重做。但关于、工具、友链、项目、专栏、TIL 和后台页面仍是 UnoCSS 加硬编码颜色和圆角的写法（例如 `admin.vue` 里的 `bg-[#0C0C0D]`、`about.vue` 里的 `rounded`）；首页画布的大标题被卡片遮住（截图 `home-1440.jpg`） |

汇总：
- **WIP 已修复 6 条**：B04 B06 B10 B13 B16 B17
- **部分修复 15 条**
- **未修复 2 条**：B20 B22
- **修复后带来新问题 3 条**：B02 B03 → B37，B11 → B27

---

## 4. 新发现问题（B24 起）

优先级：**P0** 阻断验收或安全风险 · **P1** 明显缺陷 · **P2** 打磨项。

| 编号 | 级别 | 类别 | 问题 | 证据 |
| --- | --- | --- | --- | --- |
| B24 | P0 | 启动 | `pnpm dev:api` 调用 `fastapi dev`，但依赖里没有 `fastapi[standard]`，**后端按 README 无法启动** | R1 |
| B25 | P0 | 测试与数据 | **pytest 直接使用开发库**，没有隔离：<br>· 测试创建的「自动化测试特稿草稿」（id 13）处于 **published + public** 状态，出现在首页、文章索引、RSS 和 sitemap 中<br>· 另外还有 11 篇软删除的测试文章（id 14–24）<br>· 断言依赖真实数据（`total >= 12`）<br>· `test_backup` 写入仓库的 `backups/` | DB 查询、`rss.xml`、截图 `posts-1440.jpg` |
| B26 | P0 | 可用性 | **禁用 JS 时开场遮罩永久盖住全屏**：遮罩由 SSR 输出，只有 JS 写入 `curtain-seen` 后才会隐藏。这违反 PRD 11.5 和 13.2 中「禁用 JS 时文章仍可完整阅读」 | 无 JS 实测：`.opening-curtain` 为 `display:block`，1440×900 全屏覆盖 |
| B27 | P0 | Hydration | WIP：只要主题模式不是「自动」或时段不是「昼」，**所有前台页面**都会出现 hydration 不一致：`useTheme()` 在 setup 阶段读取 localStorage 和当前小时，SSR 输出的是默认值 | R2 |
| B28 | P0 | 数据迁移 | **没有任何 Alembic 迁移**（`alembic/versions` 目录不存在）：<br>· `env.py` 没有导入模型，autogenerate 会得到空差异<br>· `DATABASE_URL=./data/blog.db` 在 alembic 下是按 `apps/api` 解析的，会迁移到错误的文件<br>· WIP 新增的 `post_likes` 只能靠 `create_all` 创建<br>· `deploy.sh` 中的 `alembic upgrade head \|\| true` 会吞掉失败<br>· 模型与 PRD 第 8 节差距很大：缺 `projects.package_url/open_issues/pushed_at/github_synced_at/cover_media_id/gallery_json`，`tils` 缺 status、published_at 和标签关联表，缺 `post_revisions`、`media_usages`、`pages`、`page_views`、`daily_stats`、`audit_logs`、`redirects`、`search_index`，`likes` 结构与 PRD 不同，枚举字段（如 comments.status）没有 CHECK 约束 | R9；`ls alembic` |
| B29 | P0 | 后端 | 后台多处返回 500：<br>· status、visibility、layout_variant 不校验枚举，直接撞上 CHECK 约束<br>· PATCH slug 不检查唯一性<br>· `delete_media` 引用了未定义的 `datetime/timezone`（`NameError`）<br>· 500 不走统一错误格式<br>ruff 报告 8 处 F821（未定义名称），mypy 报告 10 处错误 | R10 |
| B30 | P0 | 安全 | `/admin/media/upload-dev` 直接使用客户端传来的 `cos_key` 拼接路径（`DEV_MEDIA_DIR / cos_key`），**可以路径穿越写任意文件**（需要登录）；没有 MIME、扩展名和大小白名单；允许 SVG | `routers/admin/media.py` |
| B31 | P0 | COS | 配置了 COS 时，STS 返回的是写死的 `mock_sts_id/mock_sts_key`。**生产环境无法上传**；项目没有 `qcloud-python-sts` 和 `cos-js-sdk-v5` 依赖；登记接口不做 HEAD 校验；健康检查不检测 COS 是否可达 | `services/cos.py` |
| B32 | P0 | 鉴权 | access token 存在 localStorage（PRD 要求只存内存，有 XSS 外泄风险）。**登出请求不带 Authorization**，返回 401，`token_version` 不自增，refresh token 仍然有效。refresh cookie 没有 `Secure`。登录只按账户锁定、不按 IP 限流，任何人连错 5 次就能把管理员锁 15 分钟 | `layouts/admin.vue`；响应头实测 |
| B33 | P1 | 评论 | 评论默认 approved，后台没有审核界面；限流可以用 UA 绕过；没有敏感词过滤；前端用正则渲染；邮件通知缺失 | 见 B18、B21 |
| B34 | P1 | 搜索 | 内存全量扫描加子串计分，误命中多、召回差（见 B19 的实测数据）；没有 FTS5、`rebuild-search` 命令和增量索引；只能搜文章 | — |
| B35 | P1 | 运维 | `scheduler` 容器的命令是 `python -m app.cli`，不带子命令会打印帮助后退出，配合 `restart: always` 会**无限重启**；没有 APScheduler 依赖，没有 `jobs/` 目录。PRD 12.4 的 7 个定时任务一个都没有实现 | `docker-compose.yml` |
| B36 | P1 | 性能 | 首页首屏 JS 253 KB gz，超过 180 KB 预算，其中 Shiki 预取约 94 KB；4 个阻塞渲染的 CSS（站点 CSS 3 个 + Google Fonts）；移动端 Lighthouse 只有 55/56；生产 Node 服务没有开启 `compressPublicAssets` | 第 6 节 |
| B37 | P1 | 画布（WIP） | 景深系数和取模叠加，**拖动后卡片之间的相对位置会漂移并重叠**（1440 下重叠从 1 增加到 3，2560 下从 1 增加到 5）；**卡片压住中心大标题**；空闲 3 秒后会**一直漂移**（违反 PRD 3.1「有因果」，ticker 也无法空闲）；SSR 只输出标题回退内容，**没有输出列表视图的完整 HTML**（PRD 5.1 SEO）；项目卡使用硬编码颜色 `#111113/#F5C451` | `canvas-after-drag-*.png`、`home-1440.jpg` |
| B38 | P1 | 响应式 | 360px 下首页底部控制条溢出，出现横向滚动条（364/360），「文章 / 项目 / 列表视图」逐字竖排换行 | `home-360.jpg` |
| B39 | P1 | 配置 | `/site` 接口是写死的字典，后台设置的 PATCH 不会生效到前台；页脚 ICP 写死，公安备案号没有链接；控制台彩蛋写着 “Nuxt 4”（实际是 3.21） | `routers/public/site.py` |
| B40 | P1 | 种子数据 | `cli seed` **根本不创建文章**（现有文章来源未知）；文章正文约 300 字，没有覆盖扩展语法和 5 种模板；TIL 只有 6 条（PRD 要求 20 条）；没有封面（`cover_media_id` 全部为空）；没有评论种子；管理员默认密码 `admin123456` 写在 CLI 里 | DB 查询 |
| B41 | P1 | 公开接口 | `/series/{slug}` 不过滤 `deleted_at` 和 `visibility`，软删除和不公开的文章会出现在专栏里；`/projects` 返回完整 ORM 对象（包括 `description_md`），也不分页；`/tags/{slug}` 只返回文章；`/search` 返回的是 `results` 而不是 `items`；没有 `Cache-Control`；前端类型是手写的，没有用 openapi-typescript 生成 | 代码 |
| B42 | P1 | 统计与隐私 | 访客哈希不按天轮换盐（PRD 8.8 要求当日日期参与哈希），与第六节「sha256(IP+UA+盐)」的说法冲突（见 D5）；没有 `page_views` 和 `daily_stats`，后台仪表盘拿不到 PV/UV；开发环境里 Nitro 原样转发客户端的 XFF，可以伪造 | `core/visitor.py`、`server/utils/content.ts` |
| B43 | P1 | 文章页 | 终端块每行之间多一个空行（`display:block` 的 span 之间又用 `\n` 连接）；正文列和文末评论列在 1440 下左边缘相差约 48px；≤1024px 没有阅读设置面板；没有过时提醒的配置项；版权协议写死 | `article-1440.jpg` |
| B44 | P2 | 列表 | 置顶文章排在第一位但没有任何标识，看起来像排序错误；首页列表视图的悬停用 `padding-left` 做动画，触发重排 | `posts-1440.jpg` |
| B45 | P1 | 工程质量 | `apps/web` 没有 `tsconfig.json`、ESLint 配置和任何测试；Python 开发依赖没有装进 venv；ruff 报 75 处问题；页面里大量使用 `any`（PRD 要求禁止 `any`） | R6–R8 |
| B46 | P1 | 安全与 SEO | 页面响应没有 CSP、nosniff、Referrer-Policy、HSTS 等安全头；生产环境公开 `/api/v1/docs`；RSS 只输出摘要，不是全文；没有 JSON-LD；没有 canonical | `curl -I` |
| B47 | P2 | 动效 | 没有注册 CustomEase，GSAP 动画使用 `expo.out`、`power3`、`elastic` 等，不是 PRD 3.2 的同名 Token；`MOTION_DUR` 与 CSS Token 是两份数据；页面转场是 CSS 淡入淡出，不是 PRD 3.5 的强调色遮罩，也没有用 Pinia 管理状态；全局 `gsap.config({ nullTargetWarn:false })` 会掩盖错误 | 代码 |
| B48 | P2 | 后台体验 | 后台编辑器是 `<textarea>`，没有 CodeMirror、自动保存、IndexedDB 草稿和修订版本；6 处 `alert`/`confirm`；颜色硬编码；没有 Reka UI；没有 Toast | 代码 |
| B49 | P2 | 依赖 | 声明了 `lucide-vue-next`、`@vueuse/*`、`pinia`，但几乎没有使用（项目里没有 `stores/` 目录）；项目使用 Nuxt 3.21 + compat v4，PRD 要求 Nuxt 4（你已知情，仅作记录） | `package.json` |

---

## 5. PRD 功能完成度表（第 4、5、6、9、10 节）

状态以 WIP 为准。✅ 已完成 · ◐ 部分完成 · ✖ 缺失 · ≠ 与 PRD 不符。

### 第 4 节 信息架构

| 章节 | 功能 | 状态 | 说明 |
| --- | --- | --- | --- |
| 4.1 | `/` 首页画布 + SSR 列表 + 60s SWR | ◐ | 画布可用，但没有 SSR 列表（B37），没有 SWR routeRules |
| 4.1 | `/posts` | ◐ | 年份写死，后退不同步（B22），不能按专栏筛选，没有无限加载和 `?page=` 分页 |
| 4.1 | `/posts/:slug` + 300s SWR + 发布失效 | ◐ | 已改为服务端渲染，但没有 SWR，也没有 `_revalidate` |
| 4.1 | `/series`、`/series/:slug` | ◐ | 页面存在，没有阅读进度和已读打勾 |
| 4.1 | `/tags/:slug` | ◐ | 只有文章，没有项目和 TIL |
| 4.1 | `/archive` 时间河流 | ≠ | 纵向列表，不是横向时间轴（M9） |
| 4.1 | `/projects`、`/projects/:slug` | ◐ | 没有 GitHub 同步，客户端仍在用 Shiki |
| 4.1 | `/til`、`/til/:id` | ◐ | 没有单条页 `/til/:id` |
| 4.1 | `/uses` | ◐ | 内容写死，没有走 `/pages` |
| 4.1 | `/about` | ◐ | 内容写死；没有技术栈周期表、SVG 时间线和邮箱混淆 |
| 4.1 | `/now` | ✖ | P2 |
| 4.1 | `/links` | ✅ | — |
| 4.1 | `/search?q=` | ✖ | B20 |
| 4.1 | RSS / Atom / JSON Feed | ≠ | 只有摘要，不是全文 |
| 4.1 | sitemap / robots | ◐ | robots 已屏蔽 `/admin`、`/api`；sitemap 有 `lastmod`，但包含测试文章，也没有项目、标签和 TIL 页面 |
| 4.1 | 404 页 | ◐ | 有终端风格文案，但按钮文字换行，没有推荐文章 |
| 4.2 | 后台路由（11 个） | ◐ | 已有 login、仪表盘、posts、til、media、links、settings；缺 projects、taxonomy、comments、pages、`posts/new` |
| 4.3 | 顶栏隐藏与显示 | ✅ | — |
| 4.3 | 文章页顶栏显示当前章节 | ✖ | — |
| 4.3 | 命令面板 `>` 命令 / `#` 标签 | ◐ | `>` 已实现，`#` 没有；只搜文章；回车跳到 404 的 `/search` |
| 4.3 | 连续阅读下拉进入下一篇 | ✖ | P1 |
| 4.4 | 快捷键 ⌘K、/、T、M、Esc、L、0、方向键 | ✅ | — |
| 4.4 | 快捷键 `?`、J/K | ✖ | — |
| 4.5 | `POST /api/_revalidate` | ✖ | — |

### 第 5 节 前台功能

| 章节 | 功能 | 状态 | 说明 |
| --- | --- | --- | --- |
| 5.1 | 拖拽、触控、惯性、无限循环 | ◐ | 纵向滚轮不平移，有重叠（B37） |
| 5.1 | 三种卡片（封面、编号、Star、代码纹理） | ◐ | 没有真实封面，项目卡没有代码纹理 |
| 5.1 | 悬停其余卡片 0.4、速度缩放与倾斜 | ◐ | 悬停变淡已实现；速度效果只是整体缩放 |
| 5.1 | 筛选 Flip 重排 | ≠ | 只是变淡 |
| 5.1 | 列表视图悬停封面跟随光标 | ✖ | — |
| 5.1 | 首访引导（3 秒一次） | ≠ | 变成了永久漂移 |
| 5.1 | 视口裁剪、480px 缩略图、手动坐标 | ◐ | 已有视口裁剪；缩略图和手动坐标没有 |
| 5.2 | 杂志目录、悬停右移、封面跟随、多选筛选、URL 同步、Flip、无限加载 | ◐ | 只做了单选标签和年份 |
| 5.3 | 标题区（编号、日期、字数、专栏位置） | ✅ | 专栏没有「/总数」 |
| 5.3 | 排版模板 standard、wide、immersive、essay、showcase | ◐ | 只是 class 区分；immersive 没有头图视差，showcase 没有横向滚动 |
| 5.3 | Markdown 扩展（共 16 项） | ◐ | 已有：GFM、文件名、行高亮、diff、focus、alerts、terminal。缺：code-group、脚注边注、KaTeX、Mermaid 渲染、details、图片 `{width}`、gallery、github 卡片、embed、kbd 样式、showLineNumbers |
| 5.3 | 代码块体验 | ◐ | 见 B08 |
| 5.3 | 阅读进度、记住位置、阅读设置、灯箱 | ◐ | 进度和位置已实现；阅读设置缺行宽和动效开关；灯箱没有缩放和左右切换 |
| 5.3 | 划词菜单、标题锚点、外链 ↗、过时提醒 | ◐ | 锚点、外链、过时提醒已实现；没有划词菜单 |
| 5.3 | 点赞粒子、分享（X、微博、二维码） | ◐ | 已有点赞粒子和复制链接 |
| 5.4 | 专栏卡、目录、已读、上下章 | ◐ | — |
| 5.5 | 标签页混排三类内容 | ◐ | 只有文章 |
| 5.6 | 横向时间轴、统计、热力图 | ≠ | 有统计；热力图缺失 |
| 5.7 | 项目列表、悬停纹理、详情、GitHub 同步 | ◐ | 没有同步、画廊和相关文章 |
| 5.8 | TIL 终端风格、过滤、单条链接、进订阅源 | ◐ | 没有单条页，不进订阅源，标签不是关联表 |
| 5.9 | 评论（字段、受限 Markdown、两层、审核、防垃圾、开关、本地记忆、动画） | ◐ | 见 B18、B21、B33 |
| 5.10 | FTS5 加权检索、代码标识符、高亮、最近搜索、热门 | ◐ | 见 B19、B34 |
| 5.11 | 关于页（逐行揭示、周期表、SVG 时间线、邮箱混淆） | ◐ | — |
| 5.12 | uses、links、订阅、404 | ◐ | — |
| 5.13 | 主题按钮 MorphSVG、回到顶部、阅读数开关、巨型页脚、运行天数、彩蛋 | ◐ | 有巨型页脚（没有揭开效果）和彩蛋；其余缺失 |
| 3.4 | 签名动效 M1 / M2 / M3 / M4 / M5 / M6 / M7 / M8 / M9 / M10 / M11 / M12 / M13 / M15 | M1◐ M2✖ M3✖ M4◐ M5✖ M6✅ M7◐ M8✖ M9✖ M10◐ M11◐ M12◐ M13✖ M15◐ | 13.2 要求的 11 项 P0 中，只有 M6 完整；M10 没有 2 秒颜色过渡；M4 没有 SplitText，而且标题被 overflow 裁切 |
| 3.6 | 设备三档分级、减弱动效开关、gsap.context | ◐ | 只认系统的 reduced-motion，没有站内开关，没有 detect-gpu |

### 第 6 节 管理后台

| 章节 | 功能 | 状态 | 说明 |
| --- | --- | --- | --- |
| 6.1 | Argon2id、5 次锁定 15 分钟 | ✅ | — |
| 6.1 | TOTP、`create-admin` | ◐ | 有 `create-admin`；默认密码是硬编码的弱密码 |
| 6.2 | 仪表盘 PV/UV、趋势、Top10、草稿 | ◐ | 没有统计数据源 |
| 6.3 | 编辑器三模式、CodeMirror、斜杠命令、粘贴上传、字数、自动保存、IndexedDB、修订 | ✖ / ◐ | 只有 textarea、分栏预览和本地上传 |
| 6.3 | 元信息侧栏、定时发布、发布前检查、导入导出 | ◐ | 只有基础字段 |
| 6.4 | 内容列表（筛选、批量、软删除、回收站） | ◐ | 有软删除，没有回收站和批量操作 |
| 6.5 | 项目管理 | ✖ | — |
| 6.6 | TIL 管理 | ◐ | 没有 ⌘Enter |
| 6.7 | 媒体库（分块、断点续传、引用、用量） | ◐ | 只有网格和本地上传，删除接口报 500 |
| 6.8 | 标签与专栏 | ✖ | — |
| 6.9 | 评论审核 | ✖ | — |
| 6.10 | 独立页面 | ✖ | — |
| 6.10 | 友链 | ✅ | — |
| 6.11 | 站点设置（7 组） | ◐ | 只有 6 个字段，而且前台不读取 |
| 6.12 | Reka UI、⌘K、Toast、二次确认、移动端 | ✖ / ◐ | — |

### 第 9 节 API

| 章节 | 功能 | 状态 | 说明 |
| --- | --- | --- | --- |
| 9.1 | 列表格式与 page_size≤50 | ◐ | posts 和 til 符合；projects、series、links、search 不符合 |
| 9.1 | 错误格式 | ◐ | 500 不符合（B29） |
| 9.1 | `Cache-Control` | ✖ | — |
| 9.1 | openapi-typescript | ✖ | — |
| 9.1 | 鉴权（refresh 轮换 Cookie、logout） | ◐ | B32 |
| 9.1 | 限流 | ◐ | 评论和点赞有内存限流；登录没有按 IP 限流；没有用 slowapi |
| 9.2 | 公开接口（21 个） | ◐ | 缺 `/canvas`、`/posts/{slug}/unlock`、`/likes`、`/tils/{id}`、`/stats/heatmap`、`/pages/{slug}`、`/sitemap`；`/til` 的路径与 PRD 不一致 |
| 9.3 | 管理接口（约 40 个） | ◐ | 只覆盖了 auth、posts（部分）、media（部分）、til、links、settings。缺 autosave、unpublish、restore、revisions、preflight、batch、projects、tags、series、comments、pages、stats、system 和导入导出 |

### 第 10 节 COS

| 章节 | 功能 | 状态 | 说明 |
| --- | --- | --- | --- |
| 10.1–10.3 | 桶配置、对象键规范、STS 直传流程 | ≠ | STS 是假实现（B31）；对象键规范已实现 |
| 10.4 | `<SmartImage>`、数据万象 srcset、LQIP 淡入、aspect-ratio | ✖ | 有 LQIP 计算，但前端没有使用 |
| 10.5 | 引用保护、trash 前缀、恢复 | ✖ | — |
| 10.6 | `services/cos.py` 的 8 个函数 | ✖ | 只有 2 个且不完整 |
| 10.7 | 永久密钥不出现在前端 | ✅ | 前端代码和网络请求中没有出现 `COS_SECRET`（已检索） |

统计（共 79 行，签名动效单独计）：✅ 7 · ◐ 47 · ✖ 16 · ≠ 6 · ✖/◐ 混合 2；签名动效 14 项：✅ 1 · ◐ 7 · ✖ 6。

很多 ◐ 行里包含若干缺失的子功能（例如 Markdown 扩展 16 项中缺 11 项，管理接口约 40 个中缺约 30 个），把这些子功能拆开计算后，缺失项超过 100 个。

---

## 6. 性能基线（WIP 生产构建）

> HEAD 版本未单独构建测量。如需要 HEAD 的「修改前」数据，可以在独立 worktree 中补测（见 D1）。

| 指标 | 首页 | 文章页 | 项目详情 | PRD 目标 |
| --- | --- | --- | --- | --- |
| Lighthouse 移动端性能 | **55** | **56** | 55 | 文章 ≥ 90 / 首页 ≥ 80 |
| 无障碍 / 最佳实践 / SEO | 95 / 100 / 100 | 96 / 100 / 100 | 100 / 100 / 100 | ≥ 95 / ≥ 95 / 100 |
| FCP / LCP（模拟 4G） | 13.4 s / 13.7 s | 10.5 s / 10.8 s | 16.4 s / 23.1 s | LCP ≤ 2.5 s / ≤ 2.0 s |
| TBT / CLS | 0 ms / 0 | 0 ms / 0 | 0 ms / 0 | CLS ≤ 0.05 |
| 主要瓶颈 | 阻塞渲染：Google Fonts CSS 2.3 s、站点 CSS 3 个；未压缩，可节省 336 KB；未使用 JS 148 KB | 同左 | 同左，外加 Shiki 与 wasm | — |
| 首屏 JS（gzip，load 前） | **253 KB / 11 个文件** | 151 KB / 7 个 | **680 KB / 42 个** | ≤ 180 KB |
| INP | 未测（需要真实交互） | — | — | ≤ 200 ms |

无障碍失败项：`color-contrast`（`--color-ink-faint` 在纸色背景上对比度不足）、`label-content-name-mismatch`。

### 6.1 帧率与长任务（无头 Chrome，1440×900，rAF 计帧）

| 场景 | 1 倍 CPU：平均 fps / P95 帧耗时 / >33ms 帧数 / 长任务 | 4 倍 CPU 降速：同左 |
| --- | --- | --- |
| 首页画布拖拽（3 轮 S 形，约 3 s） | 117 / 8.5 ms / 1 / 无 | 109 / 16.6 ms / 2 / [52 ms] |
| 文章页快速滚动（滚轮往返 100 次） | 116 / 8.5 ms / 2 / [182 ms] | 109 / 16.7 ms / 2 / 无 |
| 页面转场（首页与文章页往返 20 次） | 119 / 8.5 ms / 4 / [175, 51, 99 ms] | **96 / 16.6 ms / 68 / 46 个，最长 876 ms、741 ms** |

### 6.2 内存

客户端路由「首页 ↔ 文章页」往返 20 次（40 次切换），强制 GC 后 JS 堆从 4.1 MB 增长到 5.9 MB（**+1.8 MB**）。

`ScrollTrigger.getAll()` 没有挂到 window 上，无法从外部读取。代码中只有 `useSplitReveal` 使用 ScrollTrigger，并且通过 `ctx.revert()` 清理，风险较低。阶段 2 会在调试构建中暴露该值以便验收。

### 6.3 Top 10 依赖（客户端产物，gzip）

> `nuxi analyze` 在 Nuxt 3.21 下构建成功，但没有留下统计文件。下表按产物分块的特征码归类得到。

| # | 依赖 | 体积 | 是否进入首屏 |
| --- | --- | --- | --- |
| 1 | Shiki 语法与主题分包（470 个） | 2,520 KB | 项目详情页按需加载约 26 个 |
| 2 | `@shikijs/engine-oniguruma` wasm | 225 KB | 项目详情页 |
| 3 | Vue + Nuxt 运行时 + Pinia | 约 75 KB | 是（entry） |
| 4 | GSAP 核心 + ScrollTrigger | 约 40 KB | 是（entry） |
| 5 | `shiki` 核心 + `@shikijs/transformers` | 约 60 KB | 首页预取 |
| 6 | `markdown-it` + entities + linkify | 约 34 KB | 首页预取 |
| 7 | Lenis | 约 5 KB | 是 |
| 8 | 页面分块：首页（画布） | 约 14 KB | 是 |
| 9 | 页面分块：文章页 | 约 12 KB | 是 |
| 10 | `@vueuse` / `lucide`（几乎未使用） | 小于 5 KB | — |

---

## 7. 排版与响应式问题（360 / 768 / 1440 / 2560）

截图：`docs/audit/screenshots/before/<页面>-<宽度>.jpg`，自动检测结果在 `layout-report.json`。

| 页面 | 问题 |
| --- | --- |
| 首页 @360 | 出现横向滚动条（364/360）；底部控制条的按钮文字逐字竖排（B38）；没有切换到列表视图（无头环境为 fine pointer，真机为触屏时会切换，但有闪烁） |
| 首页 @1440 / 2560 | 中心大标题被卡片遮住；卡片之间有重叠；卡片带投影；首屏有 3 个视觉焦点（大标题、卡片、控制条）在抢注意力 |
| 文章页 @1440 | 正文列（x≈120）和文末区（x≈188）左边缘不对齐；终端块行距加倍；正文行宽 780px、字号 18.8px（约 41 个汉字，达标），行高 1.9（达标） |
| 文章页 @360 | 标题字号偏大，「架构：从」断行不佳（没有 `text-wrap: balance`）；代码块可以横向滚动但没有渐隐提示 |
| 文章索引 @1440 | 置顶文章排第一但没有标识；年份选择器是 12px 等宽小字，可点击区域过小；标签胶囊的密度过高 |
| 关于 / 404 / 后台登录 | 按钮文字换行（「复制联系邮箱 ✉」「← 返回空间首页」「进入控制台」）；关于页仍使用 emoji |
| 全站 | 大量 10–11px 的等宽小字（PRD 的 `--fs-micro` 是 12px）；`text-wrap: balance/pretty` 没有覆盖到所有标题和段落；硬编码颜色与 px 字号散落在各组件中；暗色模式只把图片亮度降到 0.9，阴影没有改为描边 |

---

## 8. 修复计划与工作量估计

按用户给出的阶段划分，并根据本次审计结果调整。估计单位为「人日」（AI 连续工作折算），包含测试与回归。

| 阶段 | 内容（按优先级排序） | 估计 |
| --- | --- | --- |
| **1 稳定性与安全** | 1. B24、B45 工具链：dev:api、tsconfig、ESLint、vitest 和 pytest 基础设施；**测试库隔离**与 fixture（B25）<br>2. **Alembic 基线迁移**：先把现有库标记为 baseline，再加 `post_likes` 等增量迁移，可回滚（B28）<br>3. 安全：B30 路径穿越、B32 鉴权与登出、B29 500 和枚举校验、B17 回归测试、B18 和 B33 评论（审核状态与 IP 限流）、B46 安全头与 docs 开关<br>4. B26 无 JS 遮罩、B27 hydration、B11 后台主题恢复、B12 开场遮罩、B16、B04 回归测试<br>5. B19 和 B34 搜索改为 FTS5 + bm25（需要迁移）；B20 补齐 `/search` 页面和缺失的公开接口；B21、B22<br>6. 清理测试文章（软删除，需你确认，见 D6）；pytest 覆盖每个公开接口；Playwright 覆盖 4 条主流程 | 5–6 |
| **2 性能底座** | B05 收尾（项目页与后台预览改为服务端渲染，Shiki 改为细粒度按需加载语言）；B36 字体（自托管 woff2 子集与 preload、移除 Google Fonts）、CSS 合并、压缩；B37 画布重做（统一视差、无重叠的布局算法、空出标题安全区、SSR 列表、Flip 筛选、去掉阴影）；B02、B03、B06、B07 收尾；B09、B10、B13–B15；修改前后数据 | 4–5 |
| **3 设计系统** | Token 收敛（CSS 与 `motion/tokens.ts` 单一来源）；全站替换硬编码；逐页重做（B23、B08、B38、B43、B44 与第 7 节问题）；前后截图对比 | 5–6 |
| **4 动效** | CustomEase 注册；M1、M2（Flip 共享元素）、M3（TresJS，按路由懒加载，含分级降级）、M4（SplitText）、M8、M9、M10（2 秒过渡）、M11 预览图、M12、M13、M15；页面转场遮罩与 Pinia；`/dev/motion` 集中展示；每项附 Performance 录制 | 6–8 |
| **5 功能补全** | 后台：CodeMirror 编辑器与自动保存、修订、评论审核、项目与 GitHub 同步、标签与专栏、独立页面、仪表盘统计；COS STS 真实接入（B31）；定时任务（B35）；revalidate 与 SWR；种子数据（B40）；JSON-LD 与全文 RSS | 8–10 |
| **6 验收** | PRD 13.2 与第九节逐条验收，50 次切换的内存测试，4 宽度回归 | 1–2 |

合计约 29–37 人日。阶段 1 结束后会根据实际情况重估。

---

## 9. 需要你决策的事项

| # | 事项 | 我的建议 |
| --- | --- | --- |
| **D1** | **工作区里约 4400 行未提交的 WIP 怎么处理？** | **以 WIP 为基线**，在阶段 1 开头按模块拆成若干个 Conventional Commits 提交（例如 `fix(markdown): …`、`refactor(canvas): …`）。它已经修好 7 条 B 问题，引入的问题也都已登记。<br>备选：回退到 HEAD 后从头修，或者先在独立 worktree 补测一份 HEAD 的性能基线 |
| D2 | 已有数据库不是由 Alembic 创建的。迁移方案选哪种？ | 先生成与当前模型等价的初始迁移，在现有库上执行 `alembic stamp` 标记为基线，之后的结构变更（likes、FTS5、comments.root_id 索引等）全部用增量迁移，并提供 downgrade |
| D3 | 字体托管：开发阶段也要 cn-font-split 加 COS 吗？ | 开发阶段先用仓库内自托管的 woff2 子集（Fraunces、Inter、JetBrains Mono 用 fontsource；Noto Serif SC 用 cn-font-split 本地切片）；生产环境脚本上传到 COS 的 `fonts/` 前缀。**移除 Google Fonts** |
| D4 | 点赞接口用 PRD 的 `POST /likes`（通用 content_type），还是保留现在的 `/posts/{slug}/like`？TIL 是否统一为 `/tils`？ | 以 PRD 为准：实现 `/likes` 和 `/tils`，旧路径保留 301 或别名一个版本 |
| D5 | 访客哈希：PRD 8.8 要求「按天轮换盐」，第六节写的是「sha256(IP+UA+服务端盐)」，两者冲突 | 浏览和统计用按天轮换的盐（隐私优先）；点赞去重需要跨天稳定，用不含日期的盐。两种用途分开实现 |
| D6 | 测试文章 13–24（id 13 目前公开可见）怎么处理？ | 写一个一次性的可回滚迁移或 CLI，把 id 13 软删除（只设置 `deleted_at`，不物理删除） |
| D7 | 审计过程中真实库的计数器（`view_count` / `like_count` / `post_likes`）被改动，是否回滚？ | 影响很小，建议不回滚；如果需要，可以从 `baseline.db` 还原 |
| D8 | 评论默认「先审后发」需要先有后台审核界面。阶段 1 是否先做一个最小可用的评论审核页（列表、通过、垃圾、删除）？ | 是。否则只能二选一：评论默认 pending 但没人能审，或者继续即时发布、违反 PRD |
| D9 | `/archive` 改为横向时间河流（M9）、首页画布布局算法重做，这两项属于视觉方向调整 | 阶段 3 和 4 开始前，我先提交线框或截图方案给你确认 |

---

## 附录：复现与证据

- 审计脚本保存在会话临时目录 `scratchpad/tools/`，包括：
  - `crawl.mjs`：逐页收集控制台和网络错误
  - `interact.mjs`：交互行为检查
  - `perf.mjs`：帧率、长任务和堆内存
  - `jsgz.mjs`：首屏 JS 体积
  - `shots.mjs`：截图与溢出检测
  - `lh/*.json`：Lighthouse 原始报告
- 阶段 1 会把这些脚本整理成 `scripts/audit/` 加入仓库，作为每个阶段「修改前后」对比的固定口径。
- 数据库快照：`scratchpad/db/baseline.db`（审计开始前的在线备份）。
