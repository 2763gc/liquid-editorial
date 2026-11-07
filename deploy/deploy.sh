#!/usr/bin/env bash
# Liquid Editorial 一键部署脚本 (PRD 12.2 & 12.5)
set -euo pipefail

echo "=== [1/6] 环境预检 ==="
if [ ! -f .env ]; then
  echo "错误: .env 配置文件不存在，请先复制 .env.example 并配置相关秘钥！"
  exit 1
fi

echo "=== [2/6] 数据库安全热备份 ==="
docker compose run --rm api python -m app.cli backup || echo "提示: 首次运行或容器尚未构建，跳过在线备份"

echo "=== [3/6] 构建容器镜像 ==="
docker compose build

echo "=== [4/6] 执行数据库迁移 ==="
docker compose run --rm api alembic upgrade head || true

echo "=== [5/6] 启动/更新容器服务 ==="
docker compose up -d

echo "=== [6/6] 双端健康检查 ==="
sleep 5
API_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/api/v1/health || true)
WEB_HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/api/health || true)

if [ "$API_HEALTH" = "200" ] && [ "$WEB_HEALTH" = "200" ]; then
  echo ">>> 部署成功！后端 API (200) 与前端 SSR (200) 健康检查均通过。"
else
  echo ">>> 警告: 健康检查响应异常 (API: $API_HEALTH, WEB: $WEB_HEALTH)。请查看容器日志: docker compose logs --tail=100"
fi

