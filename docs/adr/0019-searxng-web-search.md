# ADR-0019: 웹 검색에 SearXNG 를 쓴다 (로컬 실행)

- **Status**: Accepted — 사용자 확정 (2026-10-05, 2단계 작업 지시서의 '확정된 결정')
- **Date**: 2026-10-05

## Context

LLM 이 최신 정보를 근거로 답하려면 웹 검색이 필요하다. 이 프로젝트는 외부 클라우드 API 를 쓰지 않는다([ADR-0001](0001-local-llm-qwen3-5-4b.md) 이후의 로컬 원칙).

## Decision

- 검색은 **SearXNG** (여러 검색엔진 결과를 모아 주는 메타 검색엔진)를 **Docker Desktop** 으로 로컬에서 띄워 쓴다. 포트 **8888**.
- 설정은 레포 안 `searxng/` 에 둔다: `compose.yaml`(컨테이너 실행), `settings.yml`(기본 설정 위에 덮어쓰기).
  - `search.formats` 에 `json` 을 추가한다 (기본은 html 만 허용하고 JSON 요청은 403).
  - `server.limiter: false` (로컬 전용이라 봇 차단이 필요 없다).
  - `google` 엔진은 `disabled` (자동 요청을 막아서 응답이 없는 경우가 많다).
  - 포트는 `127.0.0.1:8888` 로만 연다. 인증이 없기 때문이다.
- 호출: `GET /search?q=<검색어>&format=json` → `results[].title/url/content`, 응답이 없는 엔진은 `unresponsive_engines`. FastAPI(WSL)는 `localhost:8888` 로 부른다 ([ADR-0022](0022-wsl-windows-mirrored-networking.md)).
- 코드: `src/search/` (client · service · config · exceptions). 구조는 [ADR-0021](0021-structure-message-search-tools.md).

## Considered Options

- Tavily 등 외부 검색 API: 쓰기 쉽지만 질문(검색어)이 외부로 나가고 키·과금이 생긴다. 로컬 원칙에 어긋난다.
- 직접 크롤링/검색엔진 스크래핑: 막히는 일이 잦고 유지 비용이 크다.
- SearXNG 를 WSL 에 pip 로 직접 설치: Docker 가 안 될 때의 비상 대안으로만 검토했고 쓰지 않았다.

## Consequences

- Docker Desktop 이 떠 있어야 검색된다. 꺼져 있어도 서비스는 죽지 않고 "검색 실패" 문자열이 LLM 에 간다 ([ADR-0020](0020-react-loop-rules.md)).
- 결과 품질은 켜진 엔진에 달려 있다. 이번 실측에서 `brave`(Suspended: too many requests), `duckduckgo`(CAPTCHA)가 응답하지 않았다. 그래도 나머지 엔진에서 결과 20개가 왔다. 어떤 엔진이 결과를 줬는지는 확인하지 않았다 (O-28).
- 이미지 태그는 `latest` 다. 업데이트로 설정 형식이 바뀌면 깨질 수 있다.

## Revisit when

응답 없는 엔진이 늘어 결과가 부족해질 때(엔진 추가·교체), 이미지 버전을 고정해야 할 때, 외부에 포트를 열어야 할 때(`secret_key` 교체·인증 필요).
