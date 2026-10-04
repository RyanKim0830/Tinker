# 작업 기록 (worklog)

단계마다 **만든 것 / 확인 결과 / 문제와 해결**을 적는다. 확인을 못 한 것은 못 했다고 적는다.
날짜: 2026-10-03 ~ 04.

## 현재 상태 한눈에

| 단계 | 코드 | 단위 테스트(서버 불필요) | 실서버 확인 |
|---|---|---|---|
| 0. llama-server 실행 | Windows: `scripts/llama-server-moe.ps1` / WSL 대안: `scripts/llama-server.sh` | — | 통과 (WSL 2026-10-04, Windows 2026-10-04 기동·GPU 확인). **WSL→Windows 연결은 미해결 (O-21)** |
| 1. 인프라 `llm/` | 완료 | 23개 통과 | 서버 끈 상태의 전용 예외: **통과**(진짜 닫힌 포트). 서버 켠 상태의 응답: 대기 |
| 2. 비즈니스 `chat/service.py` | 완료 | 12개 통과 | 실제 모델 기억 확인: 대기 |
| 3. 프레젠테이션 | 완료 | 22개 통과 (422·502·503 포함) | `/docs` 호출, 실모델 연동: 대기 |
| 4. 클라이언트 `cli.py` | 완료 | 8개 통과 | 터미널에서 실제 대화: 대기 |

지시서는 "각 단계는 확인을 통과한 뒤 다음 단계로" 라고 했다. 이번에는 **사용자가 서버 문제를 해결하는 동안 서버 없이 가능한 부분(코드·mock 테스트·문서)을 먼저 진행해도 된다고 허락**해서 순서를 어겼다. 위 표의 "대기" 항목이 통과하기 전에는 해당 단계를 완료로 보지 않는다.

테스트 전체: `pytest` → 65 passed, 5 deselected (integration).

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

## 128K 컨텍스트 실측 기록 (2026-10-05)

### 사용자 실측값

측정일 2026-10-05, RTX 4050 Laptop 6GB, Qwen3.6-35B-A3B Q4_K_M, `--cpu-moe`, KV q8_0. 아래는 사용자가 직접 잰 수치이며 이번 작업에서 재측정하지 않았다.

- `-c 393216`: 전용 GPU 메모리 5.7/6.0GB + 공유 GPU 메모리 1.9GB, 시스템 RAM 31.2/31.6GB(99%) → VRAM 이 넘쳐 공유 메모리로 흘러감. 사용 불가로 판단.
- `-c 131072`: 전용 GPU 메모리 3.8/6.0GB, 공유 0.2GB, RAM 17.2/31.6GB(54%) → 정상.
- 두 값의 차이로 역산하면 컨텍스트 토큰당 약 14KB (KV 캐시 + 컨텍스트에 비례하는 버퍼, 추정치).
- **서버 로그의 KV 캐시 크기(MiB)는 아직 확인하지 않았다.** 실제 35B 생성 속도·WSL 실행 시 메모리 사용량·실서버 로깅 출력도 이번에는 확인하지 않았다.
