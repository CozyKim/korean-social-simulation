# Korean Social Simulation

`nvidia/Nemotron-Personas-Korea` (100만 명) 데이터셋의 인구비례 샘플에게 시나리오를 노출하고 구조화된 반응을 받아, 정량 통계와 LLM 정성 인사이트가 결합된 리포트를 자동 생성하는 1인 탐색용 시뮬레이션 도구.

## 빠른 시작

```bash
# 의존성 설치
uv sync                                  # 코어 + CLI + 마크다운 리포트
uv sync --extra dashboard                # + Streamlit 대시보드

# HF 토큰 (rate limit 회피)
export HF_TOKEN=...

# vLLM endpoint
export VLLM_BASE_URL=http://your-vllm:8000/v1

# 시뮬 실행
uv run kss run \
  --scenario scenarios/example_ramen_ad.yaml \
  --n 200 \
  --model vllm-qwen \
  --seed 42

# 대시보드
uv run kss dashboard runs/<run-id>
```

Python에서:

```python
from korean_social_simulation import simulate, Scenario

run = simulate(
    scenario=Scenario(title="신라면 광고", stimulus="..."),
    n=200,
    model="vllm-qwen",
    seed=42,
    extra_fields={"purchase_likelihood": (int, "0~100, 구매 가능성")},
)
md_path = run.report(insights_model="vllm-qwen")
```

## 디자인 문서

- 디자인: [docs/superpowers/specs/2026-04-29-korean-social-simulation-design.md](docs/superpowers/specs/2026-04-29-korean-social-simulation-design.md)
- 구현 계획: [docs/superpowers/plans/2026-04-29-korean-social-simulation.md](docs/superpowers/plans/2026-04-29-korean-social-simulation.md)
