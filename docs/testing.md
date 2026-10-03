# 테스트

한 번 짜 두면 계속 쓰는 자산이다. 기능을 바꿀 때 "예전 동작이 안 깨졌는지"를 몇 초 안에 확인하는 것이 목적이다.

## 실행

```bash
.venv/bin/python -m pytest                    # 단위/흐름 테스트 (서버 불필요, 약 1초)
.venv/bin/python -m pytest -m integration     # 실제 llama-server 필요 (scripts/llama-server.sh 먼저 실행)
.venv/bin/python -m pytest -m "" -q           # 전부
.venv/bin/python -m pytest tests/llm -q       # 한 레이어만
```

`integration` 은 `pytest.ini` 의 `addopts` 로 기본 실행에서 빠진다.

## 전략: 레이어마다 한 칸 아래를 가짜로 바꾼다

레이어드 아키텍처라서 각 레이어를 **자기 책임만** 검증할 수 있다.

| 테스트 파일 | 대상 레이어 | 진짜 | 가짜 | 검증하는 것 |
|---|---|---|---|---|
| `tests/llm/test_client.py` | 인프라 `client` | LLMClient | `httpx.MockTransport` (llama-server) | 요청 JSON(메시지 순서·샘플링 값·stream=False), 응답 파싱, **모든 실패 경로의 예외 변환**, 응답 무가공 |
| `tests/chat/test_service.py` | 비즈니스 `service` | ChatService | `FakeLLM` (LLMClient 대역) | LLM 에 **무엇을 보내는지**(시스템 프롬프트 위치, 이력), 이력 저장 시점, 예외 변환, 이력 공유 |
| `tests/chat/test_router.py` | 프레젠테이션 `router`/`schemas` | router + FastAPI | `FakeService` (`dependency_overrides`) | 422 거절 조건, 응답 형식, 예외 → 503/502, 내부 메시지 비노출 |
| `tests/test_app_stack.py` | 세 레이어 연결 | router+service+client | `MockTransport` 만 (llama-server) | Depends 주입, 예외 사슬 전체, 이력이 요청 사이에 이어지는지 |
| `tests/test_cli.py` | `cli.py` | chat_loop/ask | `MockTransport` (서버), 주입한 입출력 | 대화 루프, 종료, 빈 줄, 오류 메시지·계속 진행 |
| `tests/integration/test_llama_server.py` | 전체 + 실제 모델 | 전부 | 없음 | thinking 없음, 한국어 답변, 기억, /chat 실제 호출 |

가짜 서버에는 `httpx.MockTransport` 를 쓴다. 코드 쪽 변경 없이 `AsyncClient(transport=...)` 로 갈아 끼우는 방식이라 별도 mock 라이브러리가 필요 없다.
"닫힌 포트에 진짜로 연결" 하는 테스트(`test_real_closed_port_*`)는 mock 이 아닌 실제 네트워크 실패를 확인한다.

## 규칙 (새 테스트 쓸 때)

1. **레이어 경계를 지킨다.** service 테스트에 httpx 가, router 테스트에 llm 모듈이 나오면 설계가 샌 것이다.
2. **실패 경로를 정상 경로만큼 쓴다.** 이 프로젝트의 핵심 약속은 "외부 에러가 내부 예외로 바뀌어 올라간다"이다.
3. **정확한 문장이 아니라 성질을 검사한다.** (LLM 답변은 매번 다르다.) 정확한 값은 우리가 만든 입출력(요청 JSON, 상태 코드, 이력 내용)에만 쓴다.
4. **상태는 새지 않게 한다.** 대화 이력은 모듈 전역이라 `tests/conftest.py` 의 `clean_history` 가 매 테스트 전후로 비운다. `LLMSettings(_env_file=None)` 로 `.env` 영향도 끊는다.
5. **버그를 고치면 그 버그를 재현하는 테스트를 먼저/같이 추가한다.**
6. 실서버가 필요하면 `@pytest.mark.integration`. 서버가 없을 때 skip 이 아니라 **실패**하도록 `llm` fixture 를 쓴다.

## 테스트가 정말 잡아내는지 확인한 기록 (변이 테스트)

테스트가 "통과한다"만으로는 믿을 수 없어서, 코드에 일부러 버그 17개를 넣고 테스트가 실패하는지 확인했다 (스크립트는 일회성, 레포에 두지 않음).
결과: **17/17 검출, 생존 0.** 넣은 버그: 이력 저장 누락, 시스템 프롬프트 위치 오류, 실패 턴 선저장, 연결/응답 예외 구분 안 함, top_k 누락, 샘플링 값 오류, ConnectError 만 변환, HTTP 상태 검사 누락, stream=True, 응답 strip, 503→500, 502→503, 빈 query 허용, 응답 키 변경, CLI 빈 줄 전송, CLI /exit 무시, CLI 연결 오류 시 종료.
큰 변경 뒤에는 같은 방식으로 다시 확인할 만하다.

## 알려진 한계

- 실제 모델 답변의 "품질"은 자동 검증하지 않는다 (사람이 대화해 보고 판단).
- 동시 요청(두 요청이 동시에 이력을 건드림)은 테스트하지 않는다 → [open-items.md](open-items.md) O-07.
- 컨텍스트 한도 초과 동작은 아직 구현하지 않아 테스트도 없다 → O-06.
