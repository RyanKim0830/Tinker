# ADR-0003: 샘플링 파라미터는 요청마다 llm/client.py 가 보낸다

- **Status**: Accepted — 구현 중 결정 ([open-items.md](../open-items.md) 참고, 사용자 검토 필요)
- **Date**: 2026-10-03

## Context

확정된 값: Qwen3.5 공식 모델 카드의 non-thinking 일반 작업 권장값 — `temperature 0.7, top_p 0.8, top_k 20, presence_penalty 1.5`. 이 값을 **어디에** 둘지는 지시서에 없었다. 서버 시작 옵션에 둘 수도, 요청에 실을 수도 있다.

## Decision

값은 `src/llm/config.py`(`LLMSettings`, 환경변수 `LLM_*` 로 덮어쓰기 가능)에 두고, `llm/client.py` 가 **요청마다** 보낸다. `scripts/llama-server.sh` 에는 샘플링 옵션을 넣지 않는다.

## Considered Options

- 서버 시작 옵션(`--temp` 등)으로 지정: 값이 두 곳(스크립트·코드)에 생기거나, 클라이언트가 값을 통제하지 못한다
- 둘 다 지정: 어느 쪽이 적용되는지 헷갈린다

## Consequences

- 값의 원천이 한 곳(`llm/config.py`)이라 변경이 쉽고 테스트로 고정된다 (`test_client.py`).
- llama-server 를 `curl` 로 직접 때릴 때는 서버 기본값(temp 0.8 등)이 적용되므로 샘플링 값이 다르다.

## Revisit when

서버를 여러 클라이언트가 공유하게 되어 서버 기본값을 통일해야 할 때.
