# ADR-0007: 엔드포인트: POST /chat 하나, 스트리밍 없음

- **Status**: Accepted — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

첫 단계 목표는 터미널에서 대화가 이어지는 챗봇이다.

## Decision

`POST /chat` 하나. 요청 `{"query": str}`, 응답 `{"reply": str}`. **전체 응답을 한 번에 반환**한다 (추후 SSE 로 변환 예정).

## Considered Options

- 처음부터 스트리밍(SSE): 이번 단계 범위 밖(open-items O-08)

## Consequences

- 긴 답변은 끝까지 기다려야 한다 (타임아웃 120초 → O-11).

## Revisit when

스트리밍 구현 단계가 되면 이 ADR 을 Superseded 로 바꾸고 새로 쓴다.
