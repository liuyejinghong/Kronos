/**
 * 本地会话令牌共享助手（P19 本地安全边界）。
 *
 * 后端对所有写请求（非 GET/HEAD/OPTIONS）要求 `X-Kronos-Local-Token` 头，
 * 令牌只能通过同源 GET /session-token 获取（后端不发 CORS 头，跨站页面
 * 能发请求但读不到响应，因此拿不到令牌）。该助手负责：
 * 1. 首次写请求前懒加载并缓存令牌（并发下去重为一次请求）；
 * 2. 为非安全方法的请求附加令牌头（`safeMethods` 选项可为 GET 附加，
 *    用于有付费副作用的探测接口）。
 *
 * 令牌获取失败时静默降级为不带头的请求：后端会以 403（中文提示）拒绝，
 * 由调用方的既有错误展示路径兜底。
 */

/** 后端要求的本地会话令牌请求头。 */
export const LOCAL_TOKEN_HEADER = "X-Kronos-Local-Token";

let cachedToken: string | null = null;
let inflight: Promise<string | null> | null = null;

async function fetchSessionToken(base: string): Promise<string | null> {
  try {
    const response = await fetch(`${base}/session-token`, { cache: "no-store" });
    if (!response.ok) return null;
    const data = (await response.json()) as { token?: unknown };
    return typeof data.token === "string" && data.token ? data.token : null;
  } catch {
    return null;
  }
}

async function localToken(base: string): Promise<string | null> {
  if (cachedToken) return cachedToken;
  inflight ??= fetchSessionToken(base).finally(() => {
    inflight = null;
  });
  cachedToken = await inflight;
  return cachedToken;
}

/**
 * 返回附带本地会话令牌头的 RequestInit。安全方法（GET/HEAD/OPTIONS）默认
 * 原样返回；`safeMethods: true` 时对它们也附加令牌（付费探测接口需要）。
 */
export async function withLocalToken(
  base: string,
  init: RequestInit | undefined,
  options?: { safeMethods?: boolean },
): Promise<RequestInit> {
  const method = (init?.method ?? "GET").toUpperCase();
  const isSafeMethod = method === "GET" || method === "HEAD" || method === "OPTIONS";
  if (isSafeMethod && !options?.safeMethods) return init ?? {};
  const token = await localToken(base);
  if (!token) return init ?? {};
  return {
    ...(init ?? {}),
    headers: {
      ...(init?.headers ?? {}),
      [LOCAL_TOKEN_HEADER]: token,
    },
  };
}
