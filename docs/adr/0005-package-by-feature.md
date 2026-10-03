# ADR-0005: 기능별 패키징 (Package by Feature)

- **Status**: Accepted — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

파일을 레이어별(`routers/`, `services/`)로 모을지 기능별로 모을지 정해야 한다. 앞으로 일정·메모 등 기능이 늘어날 개인 비서다.

## Decision

기능 단위 폴더에 그 기능의 파일을 모은다: `src/chat/`(router·schemas·service), `src/llm/`(client·config·exceptions).

## Considered Options

- 레이어별 패키징: 한 기능을 고치려면 여러 폴더를 오가야 한다

## Consequences

- 기능 하나를 이해·삭제·추가할 때 한 폴더만 본다.
- 레이어는 폴더가 아니라 파일 이름(router/service/client)과 import 규칙으로 드러난다.

## Revisit when

기능 사이에 공유 코드가 많아져 순환 의존이 생기면.
