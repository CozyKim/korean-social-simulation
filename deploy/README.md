# KSS 배포

## 백엔드 (Fly.io)

### 1회 셋업

```bash
flyctl launch --config deploy/fly.toml --no-deploy --copy-config
flyctl volumes create kss_data --size 5 --region nrt
flyctl secrets set \
  KSS_OWNER_TOKEN=$(openssl rand -hex 32) \
  KSS_COOKIE_SECRET=$(openssl rand -hex 32) \
  KSS_CORS_ORIGINS=https://kss.vercel.app \
  VERCEL_REVALIDATE_HOOK_URL=https://kss.vercel.app/api/revalidate \
  VERCEL_REVALIDATE_SECRET=$(openssl rand -hex 32) \
  VLLM_BASE_URL=http://your-vllm-host:8000/v1 \
  VLLM_API_KEY=EMPTY
```

`KSS_CORS_ORIGINS` 는 production Vercel origin (예: `https://kss.vercel.app`).
미설정 시 기본값 `http://localhost:3000` 로 떨어져 cross-origin 요청이 차단된다.
복수 origin 은 콤마 분리 (`https://kss.vercel.app,https://staging.kss.vercel.app`).

`VERCEL_REVALIDATE_SECRET` 은 Vercel 측 `REVALIDATE_SECRET` 과 동일 값을 써야 인증 통과 (참고: `web/app/api/revalidate/route.ts`).

### codex OAuth 토큰 sync

LLM 호출용 codex OAuth 토큰은 본인 노트북에서 발급된 것을 백엔드 영속 볼륨에 한 번 동기화한다 (사이트 로그인 토큰과는 별개).

```bash
# 1) 본인 노트북에서:
uv run python -m korean_social_simulation.llm.codex_oauth login

# 2) 발급된 auth.json 을 fly volume 에 업로드:
flyctl ssh sftp shell
> put ~/.korean_social_simulation/codex_oauth/auth.json /data/codex_oauth/auth.json
> exit
flyctl ssh console -C "chmod 600 /data/codex_oauth/auth.json"
```

### 배포

```bash
flyctl deploy --config deploy/fly.toml --dockerfile deploy/Dockerfile
```

### 헬스체크

```bash
curl https://kss-api.fly.dev/api/health
# {"status":"ok","vllm":"up","active_jobs":0}
```

## 프론트엔드 (Vercel)

`web/` 디렉터리만 배포한다.

```bash
cd web
vercel link
vercel env add NEXT_PUBLIC_API_BASE_URL  # 빈 값 입력 — production 은 상대 경로 /api/* 사용
vercel env add API_BASE_URL  # https://kss-api.fly.dev (server-only, Vercel rewrites destination)
vercel env add NEXT_PUBLIC_FEATURED_RUN_ID  # 선택, 대표 run id
vercel env add REVALIDATE_SECRET  # 백엔드의 VERCEL_REVALIDATE_SECRET 와 같은 값
vercel deploy --prod
```

### cross-origin 쿠키 아키텍처

Vercel (`kss.vercel.app`) 과 Fly (`kss-api.fly.dev`) 는 별개 도메인이라
백엔드가 직접 보낸 `Set-Cookie` 는 Fly origin 에 저장되어 Vercel SSR 의
`cookies()` API 로 read 할 수 없다. 해결책은 모든 `/api/*` 요청을 Vercel
서버로 보내고 `next.config.ts` 의 rewrites 가 Fly 로 forward 하는 것:

- `NEXT_PUBLIC_API_BASE_URL` = 빈 값 → 클라이언트/SSR fetch 가 상대 경로 `/api/...`
- `API_BASE_URL` = `https://kss-api.fly.dev` → server-only, rewrites destination

이 구성에서 백엔드 응답의 `Set-Cookie` 가 Vercel proxy 를 거치므로 쿠키가
Vercel origin 에 저장 → SSR 미들웨어/`cookies()` 에서 정상 read.

dev 환경은 `NEXT_PUBLIC_API_BASE_URL=http://localhost:8001` 그대로 두면
브라우저가 직접 백엔드를 가리킨다 (이 때 `KSS_CORS_ORIGINS` 에 dev origin 추가).

## 자산 사전 생성

랜딩 hero, 카테고리 아이콘, 238장 페르소나 아바타는 한 번 생성해 git 에 커밋한다.

```bash
export OPENAI_API_KEY=sk-...
uv sync --extra image
uv run python -m scripts.generate_avatars        # 238장 (이미 있으면 skip)
uv run python -m scripts.generate_illustrations  # hero/og/favicon/카테고리 5종
git add web/public/avatars web/public/illustrations
git commit -m "assets: avatars + illustrations 일괄 생성"
```

자산 미생성 상태로도 사이트는 동작 — `<img onError>` fallback 으로 깨진 이미지가 노출되지 않는다 (Phase E codex fix).

## 운영 환경변수 표

| 이름 | 위치 | 설명 |
|---|---|---|
| `KSS_OWNER_TOKEN` | Fly secret | 본인 사이트 로그인 시크릿 |
| `KSS_COOKIE_SECRET` | Fly secret | 쿠키 서명 키 (itsdangerous) |
| `KSS_COOKIE_SAMESITE` | Fly env | `none` (cross-site Vercel↔Fly) |
| `KSS_COOKIE_SECURE` | Fly env | `true` (production HTTPS) |
| `KSS_TRUST_PROXY_HEADERS` | Fly env | `true` (Fly proxy 신뢰) |
| `KSS_CORS_ORIGINS` | Fly secret | 허용할 frontend origin (콤마 분리). 미설정 시 `http://localhost:3000` 로 fallback → production 차단. |
| `VLLM_BASE_URL` | Fly secret | 게스트 mini-run 백엔드 |
| `VLLM_API_KEY` | Fly secret | 보통 `EMPTY` |
| `VERCEL_REVALIDATE_HOOK_URL` | Fly secret | `https://kss.vercel.app/api/revalidate` |
| `VERCEL_REVALIDATE_SECRET` | Fly secret | Vercel `REVALIDATE_SECRET` 과 동일 |
| `KOREAN_SOCIAL_SIMULATION_CODEX_OAUTH_AUTH_PATH` | Fly env | `/data/codex_oauth/auth.json` |
| `KSS_RUNS_ROOT` | Fly env | `/data/runs` |
| `KSS_SCENARIOS_ROOT` | Fly env | `/data/scenarios` |
| `NEXT_PUBLIC_API_BASE_URL` | Vercel env | production 은 빈 값 (상대 경로 사용). dev 는 `http://localhost:8001`. |
| `API_BASE_URL` | Vercel env (server-only) | `https://kss-api.fly.dev` — Vercel rewrites destination. |
| `NEXT_PUBLIC_FEATURED_RUN_ID` | Vercel env | 대표 run id (선택) |
| `REVALIDATE_SECRET` | Vercel env | Fly `VERCEL_REVALIDATE_SECRET` 과 동일 |

## 단일 인스턴스 제약

JobManager 가 in-memory 라 백엔드 워커 1개로만 운영. `min_machines_running = 1` 유지. 다중 인스턴스 운영을 원하면 후속 Redis-based JobManager 마이그레이션 필요 — spec §13 항목.
