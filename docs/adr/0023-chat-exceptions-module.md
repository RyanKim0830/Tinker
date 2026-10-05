# ADR-0023: chat 예외를 `chat/exceptions.py` 로 분리

- **Status**: Accepted — 사용자 확정 (2026-10-05, 리팩토링 중 결정). [ADR-0012](0012-llm-exceptions.md)·[ADR-0021](0021-structure-message-search-tools.md) 의 구조(패키지마다 `exceptions.py`)를 `chat` 에도 적용한다.
- **Date**: 2026-10-05

## Context

`ChatUnavailableError`·`ChatFailedError` 가 `chat/service.py` 안에 정의돼 있었다. 그런데 `llm`·`search` 의 예외는 각자 `exceptions.py` 에 있어서 같은 종류의 코드가 두 방식으로 흩어져 있었다. 또 이 클래스들은 규칙을 판단하는 코드가 아니라 서비스와 라우터 사이의 계약(서비스가 무엇을 던지는가)이라서, 비즈니스 로직 파일에 둘 이유가 없다.

## Decision

두 예외를 `src/chat/exceptions.py` 로 옮긴다. 클래스 이름·의미·상속(둘 다 `Exception` 직속)은 그대로다.

- `service.py` 는 `exceptions` 에서 import 해서 `_call_llm` 에서 던진다.
- `router.py` 와 테스트는 `src.chat.exceptions` 에서 import 한다. `service.py` 에서 다시 내보내지 않는다.
- 예외 변환 규칙(`LLMConnectionError → ChatUnavailableError → 503`, 그 외 `LLMError → ChatFailedError → 502`)은 바뀌지 않았다.

## Considered Options

- `service.py` 에 그대로 둠: 라우터가 서비스 모듈에서 예외를 import 하게 되고, `llm`·`search` 와 구조가 어긋난다.
- `service.py` 에서 re-export: import 경로가 두 개가 되어 어디서 오는지 흐려진다. 호출처가 3곳뿐이라 직접 고쳤다.
- `ChatError` 부모 클래스 추가: 지금 둘을 한꺼번에 잡는 곳이 없다. 필요 없는 확장 포인트를 만들지 않는다 ([ADR-0013](0013-no-judgment-in-code.md)).

## Consequences

- 패키지마다 `exceptions.py` 가 있다는 규칙이 `llm`·`search`·`chat` 에 일관되게 적용된다.
- 예외를 추가할 때 `service.py` 를 열 필요가 없다.
- 예외 클래스를 `chat.service` 에서 import 하던 외부 코드는 깨진다 (이 레포 안에서는 라우터와 테스트를 같은 변경에서 고쳤다).

## Revisit when

`chat` 예외가 늘어 공통 부모가 필요해질 때, 또는 `chat` 아래에 하위 기능 패키지가 생겨 예외를 나눠야 할 때.
