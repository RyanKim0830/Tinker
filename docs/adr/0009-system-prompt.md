# ADR-0009: 시스템 프롬프트

- **Status**: Superseded by [ADR-0020](0020-react-loop-rules.md) (문구에 날짜와 검색 규칙 추가) — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

비서의 역할과 말투를 정해야 한다.

## Decision

`"너는 사용자의 개인 비서다. 한국어로 짧게 답한다."` — `chat/service.py` 의 `SYSTEM_PROMPT`(비즈니스 규칙). 이력에 저장하지 않고 **호출마다 맨 앞에 붙인다.**

## Considered Options

- 설정 파일/환경변수로 분리: 지금은 값 하나라 과함

## Consequences

- 프롬프트를 바꾸려면 코드를 수정한다 (테스트 `test_system_prompt_is_confirmed_text` 도 같이).

## Revisit when

프롬프트가 길어지거나 자주 바뀌면 파일/설정으로 분리.
