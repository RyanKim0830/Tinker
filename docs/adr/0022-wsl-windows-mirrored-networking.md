# ADR-0022: WSL(FastAPI) → Windows(llama-server, SearXNG) 연결은 WSL mirrored 네트워킹

- **Status**: Accepted — 사용자 확정 (2026-10-05, 대화에서 "맞아 그거"로 확인). [ADR-0015](0015-llama-server-on-windows.md) 가 남긴 연결 방식 미결(O-21)을 해결한다.
- **Date**: 2026-10-05

## Context

[ADR-0015](0015-llama-server-on-windows.md) 에서 llama-server 를 Windows 에서 돌리기로 했는데, 기본 NAT 모드의 WSL 에서는 Windows 의 `localhost` 가 안 보여서 연결이 안 됐다 (실측 2026-10-04, O-21). 2단계에서는 Docker Desktop(Windows)의 SearXNG 까지 같은 경계를 넘는다.

## Decision

`%UserProfile%\.wslconfig` 에 `[wsl2]` / `networkingMode=mirrored` 를 설정해 WSL 과 Windows 가 `localhost` 를 공유한다. 이 PC 에는 이미 설정돼 있다 (2026-10-05 확인).
- FastAPI(WSL)는 `http://localhost:8080`(llama-server)와 `http://localhost:8888`(SearXNG)를 부른다. 코드의 기본값 `LLM_BASE_URL`, `SEARCH_SEARXNG_URL` 그대로이고 `.env` 설정이 필요 없다.
- 서버들은 `127.0.0.1` 바인딩 그대로라 외부에 열리지 않는다.

확인한 것 (2026-10-05, 실서버): WSL 에서 `localhost:8080/health` → ok, `localhost:8888/search?format=json` → results 20개, 실제 CLI 대화(검색 포함) 성공.

## Considered Options

- NAT 유지 + 호스트 IP (`--host 0.0.0.0`, 방화벽 허용): WSL 재시작마다 IP 가 바뀌고, 인증 없는 서버가 네트워크에 열린다.
- llama-server 를 WSL 로 복귀: 대안으로는 남아 있지만 현재 기본이 아니다.

## Consequences

- WSL 전체의 네트워크 설정이 mirrored 로 바뀐 상태다 (Windows 11 22H2 이상 필요).
- Docker Desktop 이 같은 PC 에서 WSL 백엔드를 쓰므로 WSL 상태 변화(`wsl --shutdown`)가 Docker 에도 영향을 준다. 2026-10-05 에 Docker 데이터 디스크 손상으로 Docker 가 안 뜬 일이 있었지만 mirrored 와는 무관했다 ([worklog](../worklog.md)).

## Revisit when

`.wslconfig` 를 바꾸거나 다른 PC 로 옮길 때, 서버를 외부에 열어야 할 때.
