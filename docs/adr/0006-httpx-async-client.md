# ADR-0006: HTTP 클라이언트: httpx AsyncClient (OpenAI SDK 미사용)

- **Status**: Accepted — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

llama-server 는 OpenAI 호환 API 를 제공한다. 서버 호출(llm/client.py)과 CLI(cli.py)가 둘 다 HTTP 를 호출한다.

## Decision

**httpx `AsyncClient`** 로 직접 호출한다. **OpenAI SDK 는 쓰지 않는다** — 요청/응답 형식 변환을 인프라 레이어에서 직접 구현하기 위해서다.

## Considered Options

- OpenAI SDK: 편하지만 형식 변환이 SDK 안에 숨고, 서버 확장 필드(`top_k`) 다루기가 번거롭다
- requests/aiohttp: 이미 async + 테스트용 `MockTransport` 가 있는 httpx 가 더 낫다

## Consequences

- 형식 변환(`Message` ↔ JSON)을 직접 유지보수한다.
- 테스트는 `httpx.MockTransport` 로 네트워크 없이 가능하다.

## Revisit when

llama-server 이외의 OpenAI 호환 서버·클라우드로 확장해 형식 차이가 많아지면.
