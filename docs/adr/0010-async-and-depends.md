# ADR-0010: 라우터와 LLM 호출은 async, LLM 클라이언트는 Depends 로 주입

- **Status**: Accepted — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

LLM 호출은 느린 I/O 다. 이벤트 루프를 막으면 안 되고, 테스트에서 클라이언트를 바꿔 끼울 수 있어야 한다.

## Decision

라우터와 LLM 호출은 모두 `async`. `LLMClient` 는 FastAPI `Depends(get_llm_client)` 로 주입한다. 서비스는 `Depends(get_chat_service)` 로 만들어진다.

## Considered Options

- 전역 객체 직접 import: 테스트에서 교체가 어렵다

## Consequences

- `dependency_overrides` 로 레이어 테스트가 쉽다.
- 구현 중 결정: `LLMClient`·`AsyncClient` 는 프로세스당 1개를 공유하고 서버 종료 때(lifespan) 닫는다. 이력 리스트는 모듈 전역이다 (O-14).

## Revisit when

여러 프로세스/워커로 돌리게 되면 이력 보관 위치부터 다시 정해야 한다.
