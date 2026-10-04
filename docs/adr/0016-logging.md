# ADR-0016: 표준 logging 으로 요청·응답과 처리된 예외를 기록한다

- **Status**: Accepted
- **Date**: 2026-10-05

## Context

LLM 연결 실패와 이상 응답의 원인, 요청 소요 시간을 확인할 로그가 필요하다. uvicorn 도 표준 logging 을 사용한다. 응답 내용에 판단을 넣거나 미들웨어를 추가하지 않는다 ([ADR-0013](0013-no-judgment-in-code.md), [O-09](../open-items.md)).

## Decision

- 외부 라이브러리 없이 표준 `logging` 을 쓴다. 각 모듈에서 `logging.getLogger(__name__)` 로 로거를 받는다. 공용 로거 파일·객체를 만들지 않는다.
- `src/main.py` 의 lifespan 시작에서 `logging.basicConfig` 를 한 번 호출한다. `python -m src.main` 과 `uvicorn src.main:app` 모두 이 경로를 사용한다.
- 레벨은 `AppSettings.log_level` (기본 `INFO`, 환경변수 `APP_LOG_LEVEL`), 형식은 `%(asctime)s %(levelname)-5s [%(name)s] %(message)s` 이다.
- router 가 `ChatUnavailableError` / `ChatFailedError` 를 HTTP 503 / 502 로 처리하는 지점에서 `logger.exception` 으로 traceback 을 한 번 기록한다. 메시지는 각각 `chat 실패: LLM 서버 연결 불가` / `chat 실패: LLM 서버 응답 이상` 이다. service·client 는 예외를 로깅하지 않는다.
- client 는 요청 전 INFO 에 메시지 개수, DEBUG 에 전체 payload 를 기록한다. 응답 수신 후 INFO 에 HTTP 상태와 `time.perf_counter()` 로 잰 HTTP 요청 소요 시간을 기록한다. TransportError 경로에서는 응답·예외 로그를 남기지 않는다.
- 응답 내용은 기존대로 가공 없이 반환한다. 미들웨어는 만들지 않는다.

## Considered Options

- 외부 로깅 라이브러리: 현재 필요한 기록에 표준 logging 으로 충분하다.
- 진입점의 `__main__` 에서 설정: uvicorn 명령으로 실행하면 적용되지 않는다.
- 모든 레이어에서 예외 기록: 같은 실패가 중복 기록된다.
- 로깅 미들웨어: 현재 범위와 ADR-0013 에서 제외했다.

## Consequences

- 모듈 이름과 traceback 으로 실패 지점을 찾고 요청 시간을 확인할 수 있다.
- DEBUG 에는 대화 내용을 포함한 전체 payload 가 기록된다.
- `basicConfig` 는 루트 핸들러가 이미 있으면 기존 설정을 유지한다. 강제 재설정은 하지 않는다.

## Revisit when

로그 저장·구조화·별도 출력 경로나 더 세부적인 소요 시간 측정이 필요할 때.
