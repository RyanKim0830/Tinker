# 작업 기록 (worklog)

단계마다 **만든 것 / 확인 결과 / 문제와 해결**을 적는다. 확인을 못 한 것은 못 했다고 적는다.
날짜: 2026-10-03 ~ 05.

## 현재 상태 한눈에

| 단계 | 코드 | 단위 테스트(서버 불필요) | 실서버 확인 |
|---|---|---|---|
| 0. llama-server 실행 | Windows: `scripts/llama-server-moe.ps1` / WSL 대안: `scripts/llama-server.sh` | — | 통과 (WSL 2026-10-04, Windows 2026-10-04 기동·GPU 확인). **WSL→Windows 연결은 미해결 (O-21)** |
| 1. 인프라 `llm/` | 완료 | 23개 통과 | 서버 끈 상태의 전용 예외: **통과**(진짜 닫힌 포트). 서버 켠 상태의 응답: 대기 |
| 2. 비즈니스 `chat/service.py` | 완료 | 12개 통과 | 실제 모델 기억 확인: 대기 |
| 3. 프레젠테이션 | 완료 | 22개 통과 (422·502·503 포함) | `/docs` 호출, 실모델 연동: 대기 |
| 4. 클라이언트 `cli.py` | 완료 | 8개 통과 | 터미널에서 실제 대화: 대기 |
| **2단계** 툴 콜링 + 웹 검색 (스니펫만) | 완료 (체크포인트 0~4) | 전체 190개 통과 | **통과** (2026-10-05): tools→tool_calls, SearXNG JSON, 실제 CLI 대화(검색/잡담/후속), 검색 서버 꺼진 상태. 상세는 아래 "2단계" |

지시서는 "각 단계는 확인을 통과한 뒤 다음 단계로" 라고 했다. 이번에는 **사용자가 서버 문제를 해결하는 동안 서버 없이 가능한 부분(코드·mock 테스트·문서)을 먼저 진행해도 된다고 허락**해서 순서를 어겼다. 위 표의 "대기" 항목이 통과하기 전에는 해당 단계를 완료로 보지 않는다.

테스트 전체: `pytest` → **190 passed**, 13 deselected (integration). `pytest -m integration` → **13 passed** (실제 llama-server + SearXNG, 2026-10-05). (1단계 시점은 65 passed.)

## 0단계 — llama-server 실행

### 한 것
- 모델 확인: `C:\Users\User\Downloads\Qwen3.5-4B-Q5_K_M.gguf` (3,143,656,608 바이트) 존재. `models/` 로 복사 (O-01).
- 환경 확인: GPU RTX 4050 Laptop 6GB, WSL2(Ubuntu), Windows 드라이버 546.80(CUDA 12.3), 시스템에 llama.cpp·cmake·CUDA toolkit·sudo 없음.
- llama.cpp 최신 릴리스 b11377 의 `ubuntu-cuda-12.8-x64` 바이너리 + `cudart` 런타임을 `~/llama.cpp/llama-b11377/` 에 설치.
- 옵션 이름 확인(`--help`): `-c`, `--cache-type-k/-v`, `--reasoning [on|off|auto]` 모두 지시서와 동일 → 변경 없음. `-ngl` 추가(O-03).
- `scripts/llama-server.sh` 작성: WSL 경로(`/mnt/c/...`)로 모델 지정, `LLAMA_CACHE=models/`.

### 문제와 해결
1. **`libgomp.so.1` 없음** → sudo 비밀번호가 필요해서 `apt-get download libgomp1` 후 `dpkg -x` 로 라이브러리만 꺼내 llama 폴더에 넣었다 (O-02).
2. **`CUDA error: device kernel image is invalid`** (서버 로딩 직후 크래시)
   - 원인: Windows 드라이버 546.80 은 CUDA 12.3 까지 지원. 12.8 로 빌드된 커널을 못 읽음. `GGML_CUDA_PDL=0` 우회는 PDL 확인 단계만 넘고 다음 커널에서 같은 에러.
   - 해결: 사용자가 Windows 드라이버를 **616.92(CUDA 13.4)** 로 업데이트함 (2026-10-04).
   - 예비책으로 Windows CUDA 12.4 / Vulkan 빌드를 `bin/` 에 받아 두었으나 쓰지 않았다.
3. **드라이버 업데이트 후 WSL 안의 `nvidia-smi` 가 segfault** (Windows 쪽 `nvidia-smi.exe` 는 정상). 실행 중인 WSL 이 옛 드라이버 라이브러리를 들고 있어서로 보인다. → PowerShell 에서 `wsl --shutdown` 후 WSL 재시작 필요. → 해결: `wsl --shutdown` 후 재시작하자 WSL `nvidia-smi` 정상(드라이버 615.71 / CUDA UMD 13.4).

### 실서버 확인 결과 (2026-10-04)
- `scripts/llama-server.sh` 기동: 모델 로딩 약 **21초**(`/mnt/c` NTFS 에서 읽음, 첫 실행), `/health` 200. VRAM 사용 **약 3.5GB / 6GB** (RTX 4050 Laptop) → `-ngl 99` 로 충분(O-03).
- 생성 속도 약 **43 tok/s**, 짧은 질문 응답 약 1초. 응답에 thinking 혼입 없음(`reasoning_content` 도 없음) (O-19).
- `pytest -m integration` 5개 통과. 단위 65개 통과.
- 실제 모델로 end-to-end: `/chat` 두 번째 답이 첫 대화("이름은 철수")를 기억함, 빈 query 는 422, `/docs` 200, `cli.py` 로 대화 후 `/exit` 정상 종료.
- 다음 단계 후보: 스트리밍(O-08), 컨텍스트 한도 처리(O-06).

### 실행 위치 변경: llama-server 를 Windows 로 (2026-10-04, [ADR-0015](adr/0015-llama-server-on-windows.md))
- 사용자 지시: 현재는 llama-server 를 Windows 에서 연다. FastAPI 는 그대로 WSL. WSL 에서 열던 방식은 지우지 않고 대안으로 남긴다. 코드는 안 바꾸고 문서만 갱신했다. 뒤이어 사용자가 만든 빈 `scripts/llama-server-moe.ps1` 에 Windows 실행 명령을 넣었다(`.sh` 와 같은 옵션, `--cpu-moe`). (README, architecture, ADR-0015 추가/0014 대체 표시, open-items O-02·O-17·O-20·O-21).
- 확인한 것: `bin\cuda12.4\llama-server.exe` 는 **b11377**(WSL 쪽과 같음)이고 `--reasoning`, `-ngl`, `--cache-type-k`, `--port`, `--host` 가 있다. 같은 옵션으로 Qwen3.5-4B 를 띄웠고(`.ps1` 은 `MODEL` 환경변수로 4B 지정해 기동·`/health` 200 확인, 35B 는 로드하지 않음) Windows 쪽 `/health` 200, 로딩 약 6초, VRAM 약 3.5GB (CUDA 12.4 빌드가 드라이버 616.92 에서 동작). 확인 후 서버는 껐다.
- **확인한 문제**: 같은 시점에 WSL 에서 `localhost:8080` 연결 거부, `172.27.160.1:8080` 타임아웃 (WSL 기본 NAT 모드 + 서버 `127.0.0.1` 바인딩). → **FastAPI 와 Windows llama-server 의 실제 연동은 아직 확인 못 했다.** 해결 방식은 O-21 (사용자 결정 대기).
- 확인 안 한 것: mirrored 네트워킹 적용 후 동작 (이 PC 설정을 바꾸지 않았다).
- 확인 안 한 것(추가): 35B-A3B + `--cpu-moe` 실제 기동·속도·RAM 사용량.
- 메모: `scripts/llama-server.sh` 의 기본 모델(`Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`)은 커밋 안 된 작업 중 변경이다. 문서(README·ADR-0001)는 아직 Qwen3.5-4B 기준이며 이번에 건드리지 않았다.

## 1단계 — 인프라 (`src/llm/`)

### 만든 것
`config.py`(`LLMSettings`: base_url, timeout, 샘플링 4개), `exceptions.py`(`LLMError` ← `LLMConnectionError`/`LLMResponseError`), `client.py`(`Message`, `LLMClient.chat`, Depends 용 `get_llm_client`/`close_llm_client`).

### 확인 결과
- 단위 테스트 23개 통과(`tests/llm/test_client.py`): 요청 JSON·샘플링 값·stream=False, 응답 파싱, 연결 실패 4종·HTTP 상태 4종·형식 오류 6종 → 전용 예외.
- **"서버를 끈 상태에서 전용 예외가 나는지": 통과.** mock 이 아니라 아무도 듣지 않는 실제 포트에 연결해서 `LLMConnectionError` 확인 (`test_real_closed_port_raises_connection_error`).
- **"client 단독 호출로 답이 오는지": 미확인** (서버 필요).

## 2단계 — 비즈니스 (`src/chat/service.py`)

### 만든 것
`ChatService`(이력 관리, 시스템 프롬프트 앞붙임, 실패한 턴은 이력에 안 남김), `ChatUnavailableError`/`ChatFailedError`, `get_chat_service`.

### 확인 결과
- 단위 테스트 12개 통과: 두 번째 호출이 첫 대화를 LLM 에 보내는지, 시스템 프롬프트 위치·중복, 이력 공유, 예외 변환, 실패 턴 미저장.
- "두 번째 답이 실제로 기억하는지"(실제 모델): **미확인**.

## 3단계 — 프레젠테이션 (`schemas.py`, `router.py`, `src/config.py`, `main.py`)

### 만든 것
`ChatRequest(query: min_length=1)`, `ChatResponse`, `POST /chat`(503/502 포장), `AppSettings`(APP_HOST/PORT), FastAPI 앱 + lifespan.

### 확인 결과
- 라우터 테스트 22개 통과 (`test_router.py` 16 + `test_app_stack.py` 6): 잘못된 요청(빈 객체, 키 오류, null, 숫자, 리스트, 빈 문자열, JSON 아님, 본문 없음)은 **전부 422** 이고 서비스는 호출되지 않음. `/docs` 200.
- 세 레이어를 진짜로 연결하고 llama-server 만 mock 한 흐름 테스트: 이력이 요청 사이에 이어지고, 서버 다운 → 503 뒤 복구 시 실패한 질문이 이력에 없음.
- 실제 `localhost:8000/docs` 접속: **미확인**.

## 4단계 — 클라이언트 (`cli.py`)

### 만든 것
`ask`, `chat_loop`(입출력 주입 가능), `main`. 종료 `/exit`·Ctrl+D (O-15).

### 확인 결과
- 테스트 8개 통과: 여러 턴, 종료, EOF, 빈 줄, 연결 오류 안내 후 계속, HTTP 오류 표시, 닫힌 실제 포트.
- 터미널에서 실제 대화: **미확인**.

## 테스트 품질 확인
코드에 일부러 버그 17개를 넣어 테스트가 잡는지 확인: 17/17 검출 (자세한 내용 [testing.md](testing.md)).

## 문서화
조사·채택 → [documentation-guide.md](documentation-guide.md). 구조도 [architecture.md](architecture.md), 결정 15개 [adr/](adr/), 임시결정·제외 항목 [open-items.md](open-items.md), 테스트 [testing.md](testing.md).

## 로깅·128K 컨텍스트·35B-A3B 문서 정리 (2026-10-05)

### 만든 것

- 표준 logging 도입: `APP_LOG_LEVEL` (기본 INFO), lifespan 시작에서 `basicConfig` 설정. router 의 503·502 처리 지점에서 traceback 을 한 번 기록한다. client 는 요청 메시지 개수(INFO), 전체 payload(DEBUG), 응답 HTTP 상태와 소요 시간(INFO)을 기록한다. 중간 레이어의 예외 로깅·미들웨어·응답 가공은 추가하지 않았다 ([ADR-0016](adr/0016-logging.md)).
- 두 실행 스크립트의 컨텍스트를 `131072` 로 맞추고 옵션 주석을 현재 모델 기준으로 갱신했다 ([ADR-0018](adr/0018-context-131072.md)). O-06 에 한도 처리 자체는 여전히 없음을 적었다.
- 현재 모델을 Qwen3.6-35B-A3B Q4_K_M GGUF + `--cpu-moe` 로 문서·다이어그램에 반영했다. ADR-0001 은 ADR-0017 로, ADR-0002 의 컨텍스트 결정은 ADR-0018 로 대체 표시했다.
- [공식 모델 카드](https://huggingface.co/Qwen/Qwen3.6-35B-A3B#best-practices) 의 non-thinking 권장값을 확인했다: 기존에 전송하던 4개 값은 `temperature=0.7`, `top_p=0.8`, `top_k=20`, `presence_penalty=1.5` 이다. 작업 시작 시 미커밋 변경이던 temperature 0.3 은 지시에 따라 확인된 권장값 0.7 로 맞췄다. 카드에는 `min_p=0.0`, `repetition_penalty=1.0` 도 있지만 이번에는 기존 설정·payload 의 4개 항목만 유지했다. 실제 서버의 추가 두 항목 기본값은 확인하지 않았다.
- 기존 사용자 변경인 `src/chat/service.py` 의 시스템 프롬프트는 그대로 보존했다. 최신 `origin/main` 과 로컬 `main` 이 동일함을 확인하고 `feat/logging-context-128k` 브랜치를 만들었다. 후속 지시에 따라 구현 순서와 의도별로 커밋한다. 각 커밋 대상 상태에서 integration 을 제외한 전체 pytest 를 확인한다. push·PR 은 하지 않는다.

### 사용자 실측값

측정일 2026-10-05, RTX 4050 Laptop 6GB, Qwen3.6-35B-A3B Q4_K_M, `--cpu-moe`, KV q8_0. 아래는 사용자가 직접 잰 수치이며 이번 작업에서 재측정하지 않았다.

- `-c 393216`: 전용 GPU 메모리 5.7/6.0GB + 공유 GPU 메모리 1.9GB, 시스템 RAM 31.2/31.6GB(99%) → VRAM 이 넘쳐 공유 메모리로 흘러감. 사용 불가로 판단.
- `-c 131072`: 전용 GPU 메모리 3.8/6.0GB, 공유 0.2GB, RAM 17.2/31.6GB(54%) → 정상.
- 두 값의 차이로 역산하면 컨텍스트 토큰당 약 14KB (KV 캐시 + 컨텍스트에 비례하는 버퍼, 추정치).
- **서버 로그의 KV 캐시 크기(MiB)는 아직 확인하지 않았다.** 실제 35B 생성 속도·WSL 실행 시 메모리 사용량·실서버 로깅 출력도 이번에는 확인하지 않았다.

### 확인 결과

- `caplog` 테스트 두 개 추가: 연결 불가 503 의 router ERROR 레코드와 `exc_info`, 정상 LLM 호출의 요청·응답 INFO 레코드와 소요 시간.
- `bash -n scripts/llama-server.sh` 통과. 실서버 integration 테스트는 이번 범위에서 제외한다.
- 샌드박스에서는 기존 첫 ASGI 테스트가 비동기 스레드 대기에서 멈췄다. 승인 후 샌드박스 밖에서 테스트를 실행했다. 기존 시스템 프롬프트와 테스트 기대값의 불일치는 사용자가 추가로 허용한 `tests/chat/test_service.py` 의 기대 문자열 수정으로 해결했다. 새 프롬프트는 유지했다.
- 최종 `.venv/bin/python -m pytest -q`: **67 passed, 5 deselected (integration), 1.40s**. 전체 테스트 통과.
- `APP_LOG_LEVEL=DEBUG` 환경변수 반영과 lifespan 의 `basicConfig` 호출 인자도 별도로 확인했다.
- `git diff --check`, 수정 문서의 상대 링크 확인 통과.

### 커밋별 검증

- 각 커밋 대상 index 를 별도 임시 디렉토리에 내보내 전체 pytest 를 실행한 뒤 커밋했다. 뒤 단계의 작업 트리 변경이 앞 단계 테스트에 섞이지 않게 확인했다.
- 1~3번 커밋: 각각 65 passed, 5 deselected.
- 4~11번 커밋: 각각 67 passed, 5 deselected.
- 샘플링 값은 main 과 같은 권장값이므로 해당 커밋은 출처·설명 갱신을 뜻하는 `docs` 로 기록했다.
- 기존 사용자 시스템 프롬프트 변경과 허용된 테스트 기대값 수정은 하나의 별도 `feat` 커밋으로 묶었다.

## 2단계 — 툴 콜링 + 웹 검색 (1단계: 스니펫만), 2026-10-05

브랜치 `feat/tool-calling-web-search` (main 에서 분기, push 안 함). 지시서의 체크포인트(0~4)마다 멈추고 확인받는 방식이었으나, 중간에 사용자가 "체크포인트별로 멈추지 말고 끝까지 다 짜고 말하라"고 해서 체크포인트 1~4 는 멈추지 않고 이어서 했다. 확인 항목은 체크포인트별로 그대로 수행했다.

### 커밋
| 커밋 | 내용 |
|---|---|
| `2ae821f` chore: set llama-server context to 128k | 두 스크립트 `-c 131072`, 주석·`\` 정리 |
| `b814c6a` chore: add searxng docker config | `searxng/compose.yaml`, `settings.yml` |
| `4bbeae6` refactor: move Message to src/message.py | 체크포인트 1 |
| `202e849` feat: add searxng client | 체크포인트 2 (client·config·exceptions) |
| `50d0547` feat: add web search service | 체크포인트 2 (service + 통합 테스트) |
| `1cfd9bf` feat: support tool calls in llm client | 체크포인트 3 |
| `08e1ecb` feat: add web_search tool | 체크포인트 4 (tools·config) |
| `b9e971b` feat: add react loop to chat service | 체크포인트 4 (루프·main·로깅) |
| `ab90f2f` chore: raise cli timeout | 150→450초 |
| `a0ea1b1`, `e32877c` docs | ADR / 나머지 문서. 지시서의 "문서는 마지막에 모아서" 쪽을 골랐다 (ADR 번호는 아래 머지에서 0019~0022 로 바뀜) |

지시서의 예상 흐름과 달라진 점: `feat: add searxng client`·`add web search service` 는 같은 순서, `chore: set llama-server context to 128k` 는 1번 그대로다. ADR 커밋(10번)은 문서 전체 커밋 앞에 따로 두었다.

### 체크포인트 0 — 환경
- **한 것**: 스크립트 `-c 131072`, `--jinja` 는 `--help` 에서 **기본 enabled** 라 추가하지 않음, `llama-server.sh` 마지막 `\` 제거, `searxng/` 설정 작성.
- **실서버 확인**: llama-server(b11377, `-c 131072`) 기동 → `/health` ok. `tools` 를 넣은 요청에 `finish_reason: "tool_calls"`, `arguments` 는 JSON 문자열(`{"query":"서울 날씨"}`), `content` 는 null 이 아니라 `""`. WSL 에서 `localhost:8080`·`localhost:8888` 모두 접속. SearXNG `format=json` 요청에 `results` 20개(한국어 검색 포함). 응답 없는 엔진: brave(too many requests), duckduckgo(CAPTCHA).
- **측정**: 캐시 없는 첫 요청 — 프롬프트 312 토큰 22.3초(14 tok/s), 생성 27 토큰 2.1초(12 tok/s).
- **VRAM/RAM 사용량**: 지시서가 준 실측값(전용 3.8/6.0GB, 공유 0.2GB, RAM 54%)을 ADR 에 인용했다. **이번 세션에서는 직접 측정하지 않았다.**
- **문제와 해결**:
  1. **Docker Desktop 이 안 떴다.** 처음엔 WSL/mirrored 문제를 의심했으나 로그를 보니 원인은 다른 것이었다 — 설치된 Docker Desktop 이 **4.22.1(2023)** 이었고, 데이터 디스크 `%LOCALAPPDATA%\Docker\wsl\disk\docker_data.vhdx`(2023-10-26, 1.4GB)가 **손상**돼 있었다(맨 앞 8바이트가 VHDX 시그니처 아님, 4.93.0 로그에 `invalid vhdx file`). 조치: `winget upgrade Docker.DockerDesktop` 으로 **4.93.0** 으로 올리고, 손상 디스크를 사용자가 `docker_data.vhdx.corrupt-backup` 으로 이름 변경(내가 시도한 이름 변경은 권한 확인에서 거부돼 사용자가 직접 함). 새 디스크가 만들어져 Docker 엔진 29.8.1 이 떴다. (O-32)
  2. WSL mirrored 네트워킹은 이미 설정돼 있었고(`.wslconfig`), 사용자가 O-21 의 해결 방식이 맞다고 확인했다 → [ADR-0022](adr/0022-wsl-windows-mirrored-networking.md).
- **미확인**: 128k 를 끝까지 채웠을 때의 속도·메모리.

### 체크포인트 1 — 리팩터링
- `Message` 를 `src/message.py` 로 이동, import 만 변경 (`ToolCall`·tool 필드는 쓰는 체크포인트 3 에서 추가). 기존 테스트 65개 **그대로 통과**. 테스트 import 순서도 정리.

### 체크포인트 2 — 검색 단독
- `src/search/` 전체 (client·service·config·exceptions) + 단위 테스트 38개(client 29 + service 9). 합계 103개 통과.
- **실서버 확인**: 통합 테스트 3개 통과(`tests/integration/test_searxng.py`). `search("서울 날씨")` 출력이 `[1] 서울특별시, 서울시, 대한민국 시간별 날씨 - AccuWeather (https://...)\n서울특별시, ... ` 형식으로 5개.
- **문제와 해결**: 새 테스트 파일 이름이 기존(`test_client.py`, `test_service.py`)과 겹쳐 pytest 수집 오류. `tests/` 에 `__init__.py` 가 없어서이고, 구조를 바꾸지 않고 `test_search_*.py` 로 접두사를 붙였다 (O-29).

### 체크포인트 3 — LLM 툴 지원
- `Message` 에 `tool_calls`(tuple of `ToolCall`)·`tool_call_id`, `role="tool"` 추가. `LLMClient.chat(messages, tools=None) -> Message`. tools 는 있을 때만 요청에 넣음(빈 목록도 생략). 응답 파싱(tool_calls, content null → `""`), 형식 오류는 `LLMResponseError`. finish_reason·timings 로그.
- 단위 테스트(llm 클라이언트 23→42개, +19개: 툴 전송/생략, 파싱, 여러 호출 순서, null content, tool 메시지 직렬화, 형식 오류 6종 추가). 전체 122개 통과.
- **실서버 확인**: 통합 테스트 — 실제 llama-server 에 tools 를 보내 `Message.tool_calls` 로 파싱, `assistant(tool_calls)+tool` 짝을 다시 보내 tools 없이 최종 답을 받음. 7개 통과(약 56초).

### 체크포인트 4 — 루프
- `chat/config.py`(`CHAT_MAX_TOOL_ROUNDS`, 기본 2, 1 이상), `chat/tools.py`(`TOOLS`, `run_tool`), `chat/service.py`(루프), `main.py`(검색 클라이언트 닫기, `logging.basicConfig`), `cli.py`(450초). 기존 시스템 프롬프트 상수 `SYSTEM_PROMPT` 는 `build_system_prompt(today)` 로 바뀜.
- 단위 테스트: 검색 성공 / 검색 실패→문자열 / 잘못된 툴 호출 3종 / 상한 도달 시 tools 없이 호출 / LLM 실패 시 이력 미저장(검색 후 실패 포함) / 이력의 짝 유지. 전체 **190개 통과**.
- **실서버 확인 (CLI, 서버 로그 포함)**
  - 검색이 필요한 질문 "오늘 서울 날씨 어때?" → round 1: `tool_calls=web_search {"query":"서울 날씨 2026년 10월 5일"}`, 검색 결과 20개 중 5개, round 2: tools 없이 답("비, 최저 14°C~최고 19°C, 강수확률 60%"). 답이 스니펫에서 나온 것은 맞지만 **정확성은 검증하지 않았다.**
  - 잡담 "안녕, 잘 지냈어?" → 툴 호출 없이 1 왕복.
  - 후속 질문 "아까 검색 결과 첫 번째 출처 사이트가 어디였어?" → 툴 호출 없이(round 1 `tool_calls=()`) 이력의 검색 원문에서 AccuWeather URL 을 답함.
  - **SearXNG 컨테이너를 멈추고** 같은 종류 질문 → `검색 실패(연결)` 경고 로그, 서비스는 200, LLM 이 "검색 서버에 연결할 수 없어 확인하지 못했다"고 답. 이후 컨테이너 다시 시작.
  - 로그 확인: 라운드별 content·tool_calls 원문, 검색어, 결과 개수(20/LLM 5), 응답 없는 엔진(`brave: Suspended: too many requests`, `duckduckgo: CAPTCHA`), llama-server timings.
  - 통합 테스트(실제 모델 + 실제 SearXNG) 13개 통과(약 40초).
- **측정값 (서버 로그)**

  | 구간 | 프롬프트 | 생성 | 비고 |
  |---|---|---|---|
  | 검색 질문 round 1 (툴 호출) | 18 토큰 새로 처리(캐시 334) 0.87초 | 40 토큰 1.85초 (21.1 tok/s) | |
  | SearXNG 검색 | — | — | 약 1.2초 (결과 20개) |
  | 검색 질문 round 2 (답) | 762 토큰 6.16초 (123.8 tok/s) | 66 토큰 2.58초 (25.2 tok/s) | 도구 호출부터 답까지 약 10초 |
  | 잡담 | 746 토큰(캐시 391) 4.25초 | 21 토큰 0.83초 | |
  | 후속 질문 | 27 토큰(캐시 1157) 0.53초 | 118 토큰 4.9초 (23.8 tok/s) | |

  검색 한 번이 이력에 더하는 양은 약 700~800 토큰이다.
- **미확인 / 한계**: 모델이 툴을 안 불러야 할 때 부르거나 반대로 안 부르는 비율(평가 세트 없음, O-38). 툴 호출 텍스트 누출(O-39)은 관찰되지 않았다. 새 테스트의 **변이 테스트는 하지 않았다.** 컨텍스트 한도(O-06). (샘플링 값 O-27 은 main 쪽 작업에서 공식 카드로 확인돼 해결됨.)

### 임의로 정한 것
[open-items.md](open-items.md) O-22 ~ O-32 와 [ADR-0020](adr/0020-react-loop-rules.md) 의 "임의로 정한 것" 참고. 특히 **O-23(상한 `max_tool_rounds=2` 를 "LLM 총 2번 호출, 2번째는 tools 없이"로 해석)** 은 의도와 다를 수 있어 사용자 확인이 필요하다.

### main 과 머지 (2026-10-05)
- main 에 PR #1(`feat/logging-context-128k`: 로깅, 컨텍스트 131072, Qwen3.6 문서·ADR 0016~0018, Tinker 시스템 프롬프트)이 먼저 들어가서 이 브랜치와 13개 파일이 충돌했다. 한쪽으로 덮으면 반대쪽 작업이 사라지는 충돌이라(`service.py` 는 한쪽 프롬프트 한 줄 vs 다른 쪽 루프 전체) `git merge origin/main` 으로 파일마다 합쳤다. push 는 아직 하지 않았다.
- 합친 방식: ① 시스템 프롬프트는 main 의 Tinker 페르소나를 `BASE_PROMPT` 로 쓰고 날짜·검색 규칙을 붙임. ② 로깅은 main 의 포맷·router/client 로그를 쓰고 이쪽의 라운드 로그·검색 클라이언트 닫기를 얹음(main 의 로그 테스트는 제 `finish_reason/timings` 레코드를 포함하도록 기대값 갱신, 요청 로그 문구는 그대로). ③ 스크립트 주석은 main 문구에 jinja 설명만 추가. ④ ADR: main 의 0016~0018 은 그대로 두고 이 브랜치 것을 **0019~0022 로 번호 변경**, 모델·컨텍스트가 main 의 0017·0018 과 중복인 ADR 은 삭제하고 고유 내용(`--jinja` 기본 활성 확인)은 ADR-0020 으로 옮김.
- 확인: 머지 후 단위 테스트 **192개 통과**(이전 190 + main 쪽 2). 실서버 확인은 머지 후 다시 하지 못했다(llama-server·SearXNG 가 꺼져 있음).
