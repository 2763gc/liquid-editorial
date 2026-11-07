# 后台安全

> 管理后台只有一位编辑，但它握着整站的发布权。这份文档说明登录、会话、上传与响应头各自防的是什么，以及上线前要检查的几件事。

## 1. 登录

| 环节 | 做法 |
| --- | --- |
| 密码存储 | Argon2id；参数升级后，下次登录时自动重新哈希 |
| 用户名枚举 | 用户名不存在时同样跑一次 Argon2 校验、记一次失败，响应内容与耗时与「密码错误」一致 |
| 限流 | `login_attempts` 表，15 分钟滑动窗口：同一账号 + 同一 IP 失败 5 次、同一账号失败 15 次、同一 IP 失败 30 次，任一触发返回 429 与 `Retry-After`。计数按用户名记，不存在的用户名表现相同 |
| 突发 | 进程内每 IP 每分钟 12 次，在 Argon2 之前挡掉；生产 Nginx 对登录接口另有 `limit_req` |
| 两步验证 | RFC 6238 TOTP（30 秒、6 位、SHA-1），前后各容忍一个时间片；同一时间片的验证码只能用一次。密码通过后只发一张 5 分钟的临时凭证，最多试 5 次，换到会话后作废 |
| 恢复码 | 10 个，一次性，库里只存 HMAC；用掉一个会写审计并在登录页提示剩余数量 |

## 2. 会话与令牌

- **访问令牌**：HS256 JWT，15 分钟，载荷带会话号 `sid`。每个请求都核对会话仍有效，所以「踢出设备」「退出」即刻生效，不必等令牌过期。前端只把它放在内存里，不写 `localStorage`。
- **刷新令牌**：不透明随机串 `sid.secret`，只在 `HttpOnly; SameSite=Strict; Path=/api/v1/admin/auth` 的 Cookie 里，生产环境加 `Secure`。库里只存 HMAC。
  - 每次刷新都轮换。旧令牌在 30 秒宽限期内再次出现（多个标签页同时刷新）只补发访问令牌；宽限期外再出现，判定为被盗用，整个会话吊销并写一条「危险」审计。
  - 7 天不用失效，一次登录最长 30 天。每个账号最多 10 个会话，超出的按最近使用时间淘汰。
- **CSRF**：刷新与退出只靠 Cookie 鉴权，因此要求请求头 `X-Requested-With: blog-admin`；跨站页面无法在不经 CORS 预检的情况下带上它，而 CORS 只放行站点本身。
- **空闲退出**：后台 30 分钟没有任何操作自动退出，最后一分钟底部提示；多个标签页共享活跃时间，任一处退出全部退出（`BroadcastChannel`）。
- **敏感操作**：改密码、启用 / 停用两步验证、重新生成恢复码，都要再输一次密码（启用两步验证后还要验证码或恢复码）。复核失败与登录失败共用同一套持久限流。改密与启用两步验证会让其他设备全部退出。

## 3. 上传

- 对象键只能由服务端签发：`media/年/月/<6 位随机><6 位签名>.<扩展名>`。签名绑定了签发对象与扩展名，任何一个 worker 都能独立验证，不依赖进程内存。
- 扩展名取自声明的 MIME，不看文件名；只收 JPEG、PNG、WebP、GIF、AVIF，SVG 一律拒绝。
- 文件按内容识别格式（Pillow），声明与内容不符拒收；单张 15 MB、5000 万像素（防解压炸弹）；同一个键不覆盖。
- 本地存储路径落盘前 `resolve()`，确认仍在存储目录内（防路径穿越）。
- 登记媒体时，存在本地的文件，尺寸、类型、地址都从文件本身重新识别，忽略客户端传来的值。
- `/media-dev/**` 带 `Content-Security-Policy: default-src 'none'; sandbox`：就算混进了可执行内容，也不会在本站源下运行。

## 4. 响应头

| 层 | 内容 |
| --- | --- |
| FastAPI | `nosniff`、`X-Frame-Options: DENY`、`Referrer-Policy`、`CORP: same-site`、JSON 接口 `CSP: default-src 'none'`；后台接口 `Cache-Control: no-store`；生产环境 HSTS；请求体上限（上传 15 MB 余量、后台 5 MB、公开接口 256 KB） |
| Nitro | 页面 CSP（见 `apps/web/server/middleware/security-headers.ts`）、`COOP: same-origin`、`Permissions-Policy`；后台页面 `frame-ancestors 'none'` 与 `no-store` |

CSP 的取舍：Nuxt 在页面里内联了启动脚本（运行时配置、四时光照的首帧主题），没有 nonce 时 `script-src` 只能保留 `'unsafe-inline'`。其余全部收紧：不允许外站脚本、插件、`<base>` 改写、表单外发。

## 5. 真实 IP

登录限流与审计都依赖客户端 IP。只有直连方在 `TRUSTED_PROXIES` 里（默认本机，Docker 部署加上内网网段）时，才看 `X-Forwarded-For`，并从右往左跳过受信代理，取第一个不受信的地址。Nitro 转发 `/api/v1/**` 时会改写 `X-Forwarded-For`（不用 routeRules 的 proxy，那一层在中间件之前执行，改不了请求头），客户端随手写的 XFF 无法冒充别的 IP。

## 6. 审计

`audit_logs` 记录登录、失败、退出、会话吊销、改密、两步验证变更、恢复码使用，以及内容写操作（新建 / 修改 / 发布 / 删除特稿、站点设置、TIL、友链、媒体）。同一篇稿子 5 分钟内连续保存只记一次。只存 IP 前半段与浏览器摘要，不存密码、令牌。保留 180 天；登录尝试保留 30 天。在后台「§ 06 安全」查看。

## 7. 上线前检查

1. `.env` 里 `APP_ENV=production`。此时 API 会自检：`JWT_SECRET` / `HASH_SALT_SECRET` / `REVALIDATE_SECRET` 必须各不相同、不少于 32 位、不是示例值；`SITE_URL` 必须是 https。任何一条不满足，API 拒绝启动。生成随机串：`python -c "import secrets; print(secrets.token_urlsafe(48))"`。
2. 生产环境关闭接口文档（`/api/v1/docs`）、CORS 只放行 `SITE_URL`、`/api/v1/health` 只回答存活与否。
3. 不要在生产环境运行 `seed`（里面有演示账号，生产环境会直接拒绝）。用交互方式创建管理员，密码不会留在 shell 历史里：
   ```bash
   python -m app.cli create-admin --username <名字>
   ```
4. 登录后到「§ 06 安全」启用两步验证，把恢复码存进密码管理器。
5. 丢了手机又没有恢复码：在服务器上执行 `python -m app.cli reset-mfa --username <名字>`，会停用两步验证并退出全部会话。

## 8. 已知边界

- 进程内的突发限流、两步验证临时凭证的尝试次数是每个 worker 各自计数；真正的门槛（失败次数、锁定）在数据库里，多 worker 共享。
- 两步验证密钥以明文存在 `users.totp_secret`（依赖里没有对称加密库）。数据库文件与备份需要和密钥同等保管。
- 开发环境里浏览器本身就在本机，属于受信代理，所以开发时 `X-Forwarded-For` 可以伪造；生产环境有 Nginx 在前，不受影响。
