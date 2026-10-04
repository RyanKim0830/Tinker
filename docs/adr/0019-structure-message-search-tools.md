# ADR-0019: 구조 변경 — `src/message.py`, `search` 패키지, `chat/tools.py`

- **Status**: Accepted — 사용자 확정 (2026-10-05, 2단계 작업 지시서의 '확정된 결정'). [ADR-0004](0004-layered-architecture.md)·[ADR-0005](0005-package-by-feature.md) 를 따른다.
- **Date**: 2026-10-05

## Context

툴 콜링과 검색이 들어오면서 `Message` 를 `llm` 과 `chat` 이 같이 써야 하고(툴 호출·결과도 담는다), 검색이라는 새 기능이 생겼다.

## Decision

기존과 같은 계층형(router → service → client) + 기능별 패키징을 유지한다. 의존은 위에서 아래로만.

- **`src/message.py`** (신규): `Message`, `ToolCall`. `llm/client.py` 에서 이동했다. `role` 에 `"tool"` 추가, `tool_calls`, `tool_call_id` 필드. 어느 한쪽 패키지에 두면 다른 쪽이 그 패키지를 import 해야 해서 공용 모듈로 뺐다.
- **`src/search/`** (신규, 인프라+비즈니스): `config.py`(SEARCH_*), `exceptions.py`(SearchError ← SearchConnectionError / SearchResponseError), `client.py`(SearXNG 호출), `service.py`(`search(query)` → 포맷된 문자열).
- **`src/chat/tools.py`** (신규): 툴 스키마 목록 + 툴 이름 → 실행 매핑 (`run_tool`). **`src/chat/config.py`** (신규): CHAT_* 설정. `chat/service.py` 는 ReAct 루프로 바뀌었다.
- **`llm` 과 `search` 는 서로를 모른다.** `chat` 만 둘을 엮는다.
- 패키지 간 import 는 모듈 이름을 명시한다: `from src.search import service as search_service`. (새로 쓴 코드와 `chat/service.py` 에 적용했다. 이번에 건드리지 않은 기존 import, 예: `router.py` 는 그대로다.)
- `main.py` 의 lifespan 에서 LLM·검색용 httpx 클라이언트를 모두 닫는다.

## Considered Options

- `Message` 를 `llm/` 에 두고 `chat` 이 가져다 씀(기존): 툴 호출 타입이 늘어도 되지만 `search` 쪽 결과를 담을 때 의존 방향이 어색해진다.
- `tools.py` 를 `search/` 에 둠: `search` 가 LLM 툴 형식을 알게 되어 "서로 모른다"가 깨진다.
- 레이어별 폴더로 재구성: ADR-0005 를 뒤집는다.

## Consequences

- `chat/tools.py` 가 `search` 의 서비스·예외를 알고, 검색 예외를 문자열로 바꾸는 책임을 진다.
- 툴을 추가하면 `TOOLS` 와 `_HANDLERS` 두 곳에 같은 이름으로 넣어야 한다 (테스트가 둘의 일치를 검사한다).
- 테스트 디렉터리에 `__init__.py` 가 없어서 파일 이름이 겹치면 안 된다: 검색 테스트는 `test_search_client.py`, `test_search_service.py` 로 접두사를 붙였다 (O-29).

## Revisit when

툴이 여러 개로 늘 때(핸들러 시그니처 통일), `Message` 가 더 복잡해질 때(이미지 등), 기존 코드의 import 스타일을 한꺼번에 맞출 때.
