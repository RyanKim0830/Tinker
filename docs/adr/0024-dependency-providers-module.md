# ADR-0024: Depends 제공자를 패키지별 `dependencies.py` 로 분리

- **Status**: Accepted — 사용자 확정 (2026-10-05, 리팩토링 중 결정). [ADR-0010](0010-async-and-depends.md) 의 결정(Depends 주입, 클라이언트 프로세스당 1개 공유)은 그대로이고 코드 위치만 바뀐다. [ADR-0008](0008-in-memory-history.md) 의 이력 위치(`chat/service.py`)는 이 ADR 로 `chat/dependencies.py` 가 된다.
- **Date**: 2026-10-05

## Context

FastAPI `Depends` 용 제공자(`get_llm_client`, `get_search_client`, `get_search_service`, `get_chat_service`)가 각각 만들려는 객체와 같은 파일(`client.py`, `service.py`)에 있었다. 이 때문에:

- 기능 코드와, 객체를 만들어 공유하고 닫는 코드가 한 파일에 섞여 파일의 책임이 많았다. 변경 이유가 두 가지다: 기능 규칙이 바뀔 때, 조립 방식이 바뀔 때.
- 비즈니스 레이어(`chat/service.py`, `search/service.py`)가 `fastapi` 를 import 했다. 레이어 규칙([ADR-0004](0004-layered-architecture.md))과 파일 docstring 은 "HTTP·웹 프레임워크를 모른다"고 하는데 코드가 어긋났다.
- 모듈 전역 상태(클라이언트 싱글턴 `_client`/`_http`, 대화 이력 `_history`)가 기능 파일 안에 있었다.

## Decision

패키지마다 `dependencies.py` 를 두고 제공자와 그 전역 상태를 옮긴다. 동작은 바뀌지 않는다.

| 파일 | 내용 |
|---|---|
| `llm/dependencies.py` | `get_llm_client`, `close_llm_client`, 전역 `_client`/`_http` |
| `search/dependencies.py` | `get_search_client`, `close_search_client`, `get_search_service`, 전역 `_client`/`_http` |
| `chat/dependencies.py` | `get_chat_service`, 전역 `_history` |

- 의존 방향은 `dependencies → client/service` 한쪽이다. `client.py`·`service.py` 는 `dependencies` 를 import 하지 않는다. `chat/dependencies.py` 는 다른 패키지의 `dependencies` 를 모듈 이름으로 import 한다([ADR-0021](0021-structure-message-search-tools.md)): `from src.llm import dependencies as llm_dependencies`.
- `client.py`·`service.py` 에는 `fastapi` import 가 없다.
- `main.py` 의 lifespan 은 `llm.dependencies`·`search.dependencies` 의 `close_*` 를 부른다. `router.py`·테스트의 import 경로도 바꿨다.
- 서비스(`SearchService`, `ChatService`)는 요청마다 새로 만들고, 클라이언트(`AsyncClient`)와 이력만 프로세스에서 공유한다. 이것도 이전과 같다.
- 싱글턴 구현 방식(모듈 전역 + 지연 생성 함수)은 바꾸지 않았다.
- 패키지별 테스트: `tests/llm/test_llm_dependencies.py`, `tests/search/test_search_dependencies.py`, `tests/chat/test_chat_dependencies.py`.

## Considered Options

- 지금 구조 유지(제공자를 각 파일에 둠): 파일 하나로 객체 생성까지 보이지만 위의 책임 혼재와 `fastapi` import 가 남는다.
- 프로젝트 전체에 `src/dependencies.py` 하나: 기능별 패키징([ADR-0005](0005-package-by-feature.md))과 맞지 않고 모든 패키지를 한 파일이 알게 된다.
- 순환 import 걱정: `dependencies → service/client` 한쪽 방향이라 생기지 않는다. 분리를 막는 이유가 아니었다.
- 싱글턴을 lifespan + `app.state` 로 바꾸기: 생성·종료가 한곳에 모이지만 이번 범위가 아니다. 위치만 옮겼다.

## Consequences

- `client.py`·`service.py` 는 기능 코드만 남고 `fastapi` 를 모른다. 제공자가 늘어도 기능 파일은 안 커진다.
- 객체가 어떻게 만들어지는지 보려면 `client.py` 가 아니라 `dependencies.py` 를 봐야 한다.
- `get_*`·`close_*`·`_history` 를 기능 파일에서 import 하던 코드는 깨진다. 이 레포 안에서는 `main.py`, 라우터, 테스트를 같은 변경에서 고쳤다.
- 테스트는 이력을 `dependencies._history` 로 비운다 (`tests/conftest.py`).

## Revisit when

싱글턴 생성·종료를 lifespan 으로 옮길 때, 멀티 워커로 돌려 이력 보관 위치를 다시 정할 때([ADR-0010](0010-async-and-depends.md)), 제공자 파일 하나가 길어질 때.
