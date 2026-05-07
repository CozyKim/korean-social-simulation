// 클라이언트 빌드에는 NEXT_PUBLIC_* 만 인라인된다. 운영 가이드에서는 빈 문자열로
// 두고 Vercel rewrites 로 same-origin 상대 경로를 사용하도록 안내한다.
const CLIENT_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
// 서버(SSR/Route Handler) 는 server-only API_BASE_URL 을 우선 사용한다 — 운영
// 환경에서는 빈 NEXT_PUBLIC_API_BASE_URL + 상대 경로가 Node fetch 에서 "Failed
// to parse URL" 로 즉시 실패하므로 절대 origin 이 필요하다. 양쪽 미설정 시
// fallback 으로 NEXT_PUBLIC_API_BASE_URL 을 본다 (로컬/통합 테스트).
const SERVER_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "";

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`HTTP ${status}: ${detail}`);
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${CLIENT_BASE}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }
  // 204 No Content / 빈 응답은 res.json() 호출 시 SyntaxError → undefined 반환.
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export async function apiFetchServer<T>(
  path: string,
  cookieHeader: string,
  init: RequestInit = {}
): Promise<T> {
  if (!SERVER_BASE) {
    throw new ApiError(500, "API_BASE_URL not configured for server-side fetch");
  }
  const res = await fetch(`${SERVER_BASE}${path}`, {
    headers: { Cookie: cookieHeader, ...(init.headers ?? {}) },
    cache: "no-store",
    ...init,
  });
  if (!res.ok) throw new ApiError(res.status, res.statusText);
  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  return (await res.json()) as T;
}
