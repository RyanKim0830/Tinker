# ADR-0012: llama-server 연결 실패는 llm 모듈 전용 예외로 구분

- **Status**: Accepted — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

서버가 꺼진 것과 서버가 이상한 응답을 준 것은 대응이 다르다. 윗 레이어가 httpx 를 알면 레이어 규칙([ADR-0004](0004-layered-architecture.md))이 깨진다.

## Decision

`llm/exceptions.py`: `LLMError`(부모) ← `LLMConnectionError`(연결 실패·타임아웃·전송 중 끊김), `LLMResponseError`(HTTP 오류 상태, 예상과 다른 JSON). 클라이언트가 `httpx.TransportError` 등을 이 예외로 바꿔 올린다.

## Considered Options

- httpx 예외를 그대로 올림: 레이어 규칙 위반

## Consequences

- 타임아웃도 `LLMConnectionError` 로 묶는다 (구분 필요해지면 분리 → O-11).
- 서비스·라우터의 예외 변환은 O-05.

## Revisit when

연결 실패와 타임아웃을 다르게 대응해야 할 때.
