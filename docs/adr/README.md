# 설계 결정 기록 (ADR)

결정 1개 = 파일 1개. 형식은 MADR 축약형이다 (왜: [../documentation-guide.md](../documentation-guide.md)).
결정이 바뀌면 파일을 고치지 않고 새 ADR 을 만들어 이전 것의 Status 를 `Superseded by ADR-xxxx` 로 바꾼다.

| # | 결정 | 상태 |
|---|---|---|
| [0001](0001-local-llm-qwen3-5-4b.md) | 로컬 LLM 모델: Qwen3.5-4B (Unsloth GGUF Q5_K_M) | 확정 |
| [0002](0002-inference-server-llama-server.md) | 추론 엔진: llama.cpp llama-server + 실행 옵션 | 컨텍스트 결정은 ADR-0018 로 대체 |
| [0003](0003-sampling-params-in-client.md) | 샘플링 파라미터는 요청마다 llm/client.py 가 보낸다 | 구현 중 결정 |
| [0004](0004-layered-architecture.md) | 레이어드 아키텍처 (프레젠테이션 → 비즈니스 → 인프라) | 확정 |
| [0005](0005-package-by-feature.md) | 기능별 패키징 (Package by Feature) | 확정 |
| [0006](0006-httpx-async-client.md) | HTTP 클라이언트: httpx AsyncClient (OpenAI SDK 미사용) | 확정 |
| [0007](0007-post-chat-endpoint.md) | 엔드포인트: POST /chat 하나, 스트리밍 없음 | 확정 |
| [0008](0008-in-memory-history.md) | 대화 이력: 서버 메모리의 리스트 하나, session_id 없음 | 확정 |
| [0009](0009-system-prompt.md) | 시스템 프롬프트 | 확정 |
| [0010](0010-async-and-depends.md) | 라우터와 LLM 호출은 async, LLM 클라이언트는 Depends 로 주입 | 확정 |
| [0011](0011-pydantic-settings.md) | 설정: 모듈별 pydantic BaseSettings | 확정 |
| [0012](0012-llm-exceptions.md) | llama-server 연결 실패는 llm 모듈 전용 예외로 구분 | 확정 |
| [0013](0013-no-judgment-in-code.md) | 코드에 판단을 넣지 않고, 지금 필요 없는 확장 포인트를 만들지 않는다 | 확정 |
| [0014](0014-wsl-runtime-and-paths.md) | 실행 환경: llama-server 를 WSL 에서 실행, 경로는 /mnt/c, 모델은 models/ 폴더 | 대체됨 (0015, 실행 위치 부분만) |
| [0015](0015-llama-server-on-windows.md) | 실행 환경: llama-server 는 Windows, FastAPI 는 WSL (WSL 실행은 대안으로 보존) | 확정 |

| [0016](0016-logging.md) | 표준 logging 설정과 요청·응답·예외 기록 | 확정 |

| [0018](0018-context-131072.md) | 실측에 따른 컨텍스트 131072 | 확정 |

새 ADR 은 `template.md` 를 복사해서 쓴다.
