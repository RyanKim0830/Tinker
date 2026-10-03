# ADR-0011: 설정: 모듈별 pydantic BaseSettings

- **Status**: Accepted — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

연결 주소 등 설정이 코드에 박히면 바꾸기 어렵다. 모듈이 독립적이어야 한다.

## Decision

모듈마다 자기 `config.py` 에 `BaseSettings` 를 둔다. `llm/config.py`(`LLM_*`: base_url 등), `src/config.py`(`APP_*`: 앱 공통). 값은 환경변수 또는 `.env`.

## Considered Options

- 전역 설정 객체 하나: 모듈 독립성이 깨진다

## Consequences

- `.env` 에 모듈 접두사로 값이 섞여 있다. `.env` 는 커밋하지 않는다. 기본값은 코드에 있다 (O-12).

## Revisit when

설정 항목을 공유해야 하면 `.env.example` 을 둔다.
