/**
 * /api/v1/** 反向代理到 FastAPI。
 * 不用 routeRules 的 proxy：那一层在所有中间件之前执行，没法改写 X-Forwarded-For，
 * 客户端随手写一个 XFF 就能冒充别的 IP，绕过登录限流。
 */
export default defineEventHandler((event) => {
  return proxyRequest(event, `${apiBase()}${event.path}`, {
    headers: {
      'x-forwarded-for': forwardedFor(event),
      'x-forwarded-proto': getRequestProtocol(event, { xForwardedProto: true }),
    },
  });
});
