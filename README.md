# Korean Social Simulation

[`nvidia/Nemotron-Personas-Korea`](https://huggingface.co/datasets/nvidia/Nemotron-Personas-Korea) (한국 인구 100만 명 페르소나) 데이터셋에서 **인구비례 샘플**을 뽑아 시나리오(광고/제품/정책 등)에 노출하고, 페르소나별 **구조화된 반응**을 모아 **정량 통계 + LLM 정성 인사이트 리포트**를 자동 생성하는 1인 탐색용 시뮬레이션 도구.

> "이 광고를 보면 30대 직장인은 어떻게 반응할까?", "이 정책에 비수도권 자영업자는 어떤 우려가 있을까?" 같은 질문을 N명의 가상 한국인에게 던져보는 소셜 시뮬레이터.

---

## 핵심 특징

- **인구비례 stratified 샘플링** — `(성별 × 연령대 × 지역)` strata에서 largest-remainder 방식으로 정확히 N명 추출, seed 고정으로 결정적 재현.
- **페르소나 풍부도** — Nemotron-Personas-Korea의 26개 컬럼(인구통계 + 7종 페르소나 텍스트 + 취미/스킬/진로 등)을 그대로 LLM 컨텍스트에 노출.
- **구조화 반응** — Pydantic `with_structured_output` 으로 stance/intensity/action_intent/key_drivers/concerns/quote 강제 + `extra_fields` 로 사용자 정의 필드 동적 확장.
- **백엔드 두 종** — vLLM(회사 서버) / Codex OAuth(ChatGPT) 동일 인터페이스.
- **단일 디렉터리 산출물** — `runs/<id>/` 안에 입력·반응·차트·`report.md` 까지 무손실 저장. Streamlit 대시보드로 즉시 탐색 가능.
- **async 코어** — `asyncio.gather` + `Semaphore` 로 동시 LLM 호출 수 제어, 노트북·FastAPI에서도 `asimulate(...)` 직접 await.

---

## 빠른 시작

### 1) 설치

Python 3.13+ / [`uv`](https://github.com/astral-sh/uv) 권장.

```bash
uv sync                          # 코어 + CLI + Markdown 리포트
uv sync --extra dashboard        # + Streamlit 대시보드
```

### 2) 환경 변수

```bash
# HuggingFace rate limit 회피 (선택, 권장)
export HF_TOKEN=hf_...

# vLLM 백엔드 사용 시
export VLLM_BASE_URL=http://your-vllm:8000/v1
export VLLM_API_KEY=EMPTY        # 기본 EMPTY
```

Codex OAuth 백엔드는 별도 로그인이 필요합니다 — 아래 [Codex OAuth 로그인](#codex-oauth-로그인) 절 참고.

### 3) 시뮬레이션 실행

```bash
uv run kss run \
  --scenario scenarios/example_ramen_ad.yaml \
  --n 200 \
  --model vllm-qwen \
  --seed 42 \
  --insights-model vllm-qwen          # 종합 LLM 인사이트도 같이 생성
```

완료 후 `runs/<timestamp>-<uuid>-<slug>/report.md` 가 생성됩니다.

### 4) 대시보드

```bash
uv run kss dashboard runs/<run-id>
```

Overview / Segment / Quote / Extras 탭에서 stance 분포, 세그먼트별 차트, 대표 인용문, 사용자 정의 필드 분포까지 둘러볼 수 있습니다.

---

## 시나리오 YAML

`scenarios/example_ramen_ad.yaml`:

```yaml
title: "신라면 신제품 광고"
scenario_type: marketing            # marketing | social | product | policy | other
stimulus: |
  농심에서 출시하는 신라면 매운맛 강화 신제품. 가격은 기존보다 200원 비싼 1,500원.
  "기존 라면이 시시했다면, 진짜 매운맛을 원한다면 이 한 봉지" 라는 카피와
  20대 후반 직장인이 야식으로 먹는 광고 영상.
context: |
  국내 라면 시장이 정체되고 있고, 매운맛 카테고리는 삼양 불닭볶음면이 강세인 상황.
question: "이 광고를 본 한국 소비자들은 신제품을 구매하려 할 것인가, 어떤 우려가 있을까?"
```

| 필드 | 필수 | 설명 |
|---|---|---|
| `title` | ✅ | 짧은 식별자, run 디렉터리 슬러그용 |
| `stimulus` | ✅ | 페르소나에게 실제로 노출되는 본문 |
| `scenario_type` | | 5종 enum (기본 `other`) |
| `context` | | 배경 정보 |
| `question` | | 평가 포인트 (LLM에게 전달) |

---

## Python API

### 동기 컨텍스트 (스크립트)

```python
from korean_social_simulation import simulate, Scenario

run = simulate(
    scenario=Scenario(
        title="신라면 광고",
        stimulus="...",
        scenario_type="marketing",
    ),
    n=200,
    model="vllm-qwen",
    seed=42,
    extra_fields={
        "purchase_likelihood": (int, "0~100, 구매 가능성"),
        "willing_price_krw": (int, "지불 의향 가격(원)"),
    },
)
md_path = run.report(insights_model="vllm-qwen")
print(run.df["stance"].value_counts(normalize=True))
```

### async 컨텍스트 (노트북·FastAPI·Streamlit)

```python
from korean_social_simulation import asimulate, Scenario

run = await asimulate(scenario=Scenario(...), n=200, model="vllm-qwen")
md_path = await run.areport(insights_model="vllm-qwen")
```

> 주의: 이미 이벤트 루프가 떠 있는 환경(노트북·pytest-asyncio·FastAPI 등)에서 `simulate()` / `run.report()` 동기 wrapper를 호출하면 명확한 에러로 실패합니다. `asimulate` / `areport` 를 사용하세요.

### 주요 인자

| 인자 | 기본 | 설명 |
|---|---|---|
| `n` | 200 | 샘플 크기 |
| `model` | `vllm-qwen` | `available_models()` 키 |
| `seed` | 42 | 샘플링 재현성 시드 |
| `filters` | `None` | 모집단 필터 (예: `{"province": "서울특별시"}`) |
| `action_intent_choices` | (8종 영문 enum) | Reaction의 `action_intent` 후보 오버라이드 |
| `extra_fields` | `None` | `{name: (type, "desc"), ...}` 동적 필드 추가 |
| `min_cell_threshold` | 5 | 희소 셀 경고 기준 (0이면 비활성) |
| `concurrency` | (백엔드별 기본) | 동시 LLM 호출 수 |
| `runs_root` | `runs` | 산출물 루트 |

---

## 모델 백엔드

`src/korean_social_simulation/llm/factory.py` 에 등록된 프리셋:

| 모델 ID | 백엔드 | 기본 동시성 | 비고 |
|---|---|---|---|
| `vllm-qwen` | vLLM (Qwen2.5-72B-Instruct) | 16 | `VLLM_BASE_URL` 필요 |
| `vllm-exaone` | vLLM (EXAONE-3.5-32B-Instruct) | 16 | `VLLM_BASE_URL` 필요 |
| `gpt-5.5` | Codex OAuth | 2 | OAuth 로그인 필요 |
| `gpt-5.4` | Codex OAuth | 2 | OAuth 로그인 필요 |
| `gpt-5.4-nano` | Codex OAuth | 2 | OAuth 로그인 필요 |

### Codex OAuth 로그인

ChatGPT Plus/Pro 계정 기반 OAuth로 ChatGPT 컨슈머 백엔드(`chatgpt.com/backend-api`)에 접근합니다. 일반 OpenAI API 키와는 별개입니다.

```bash
# 자동 콜백 (브라우저가 열리는 환경)
uv run python -m korean_social_simulation.llm.codex_oauth login

# 수동 (헤드리스/원격 SSH)
uv run python -m korean_social_simulation.llm.codex_oauth login --manual

# 자격증명 삭제
uv run python -m korean_social_simulation.llm.codex_oauth logout
```

자격증명은 `~/.korean_social_simulation/codex_oauth/auth.json` 에 0600 권한으로 저장되며, 만료 직전에 refresh token으로 자동 갱신됩니다. 경로는 `KOREAN_SOCIAL_SIMULATION_CODEX_OAUTH_AUTH_PATH` 로 변경 가능.

---

## CLI 레퍼런스

```bash
uv run kss --help
```

| 명령 | 설명 |
|---|---|
| `kss run --scenario PATH [...]` | 시나리오 YAML로 시뮬 실행 + `report.md` 생성 |
| `kss list [--limit N]` | 최근 run 디렉터리 목록 |
| `kss inspect runs/<id>` | run의 메타·stance 분포 출력 |
| `kss dashboard runs/<id>` | Streamlit 대시보드 실행 (extras `dashboard` 필요) |

---

## Run 디렉터리 구조

```
runs/<YYYYMMDD-HHMMSS-uuid>-<slug>/
├── scenario.json          # 입력 + meta(model/n/seed/dataset_fingerprint/sampler_version 등)
├── reactions.parquet      # 페르소나별 반응 결과 (DataFrame)
├── sample.parquet         # 추출된 페르소나 메타
├── charts/                # 세그먼트 차트 PNG
└── report.md              # 통계 + (선택) LLM 종합 인사이트
```

기존 디렉터리는 절대 덮어쓰지 않으며, 같은 run_id 충돌 시 `FileExistsError` 로 보호됩니다.

### Reaction 스키마

| 필드 | 타입 | 설명 |
|---|---|---|
| `stance` | `positive`/`negative`/`neutral`/`mixed` | 전반적 입장 |
| `intensity` | `int` 1~5 | 반응 강도 |
| `action_intent` | enum (기본 8종) | 행동 의도 (`purchase`, `advocate`, `share`, `discuss`, `seek_more_info`, `ignore`, `avoid`, `reject`) |
| `key_drivers` | `list[str]` 1~3 | 핵심 이유 |
| `concerns` | `list[str]` | 우려 포인트 |
| `quote` | `str` | 친구·동료에게 할 법한 1~2문장 |

여기에 `extra_fields` 로 `purchase_likelihood`, `willing_price_krw` 같은 필드를 동적으로 추가할 수 있습니다.

---

## 재현성

- **데이터셋**: `_version.py:DATASET_REVISION` 으로 HF 커밋 SHA 고정. 모든 run의 `meta.dataset_fingerprint` 에 결정적 해시 기록.
- **샘플링**: `(seed, dataset_fingerprint, n, filters, sampler_version)` 키로 캐시. 동일 입력은 동일 행 반환.
- **샘플러 버전**: 알고리즘이나 strata 스키마 변경 시 `SAMPLER_VERSION` bump → 기존 캐시 자동 무효화.

---

## 개발

```bash
uv sync --all-extras                 # dev deps 포함
uv run pytest                        # 기본 테스트
uv run pytest -m live                # HF 네트워크 필요 케이스
uv run ruff check . && uv run ruff format --check .
```

테스트 디렉터리:
- `tests/test_e2e.py` — end-to-end 통합 (mock LLM)
- `tests/test_simulate.py` / `test_run.py` / `test_reaction.py` / `test_scenario.py`
- `tests/data/` — 샘플러 인구비례·재현성
- `tests/llm/` — 프롬프트·factory·codex_oauth 호환성
- `tests/report/` — 차트·markdown·insights
- `tests/test_dashboard_smoke.py`

---

## 디자인 문서

- 디자인: [docs/superpowers/specs/2026-04-29-korean-social-simulation-design.md](docs/superpowers/specs/2026-04-29-korean-social-simulation-design.md)
- 구현 계획: [docs/superpowers/plans/2026-04-29-korean-social-simulation.md](docs/superpowers/plans/2026-04-29-korean-social-simulation.md)

---

## 라이선스 / 크레딧

- Codex OAuth 어댑터는 MIT-licensed [`langchain-codex-oauth`](https://github.com/AnthonyTlei/langchain-codex-oauth) 프로젝트를 참고한 in-tree 포팅입니다.
- 페르소나 데이터셋: NVIDIA — `nvidia/Nemotron-Personas-Korea` (해당 라이선스 준수).
