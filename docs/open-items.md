# 미결사항과 임시 결정

구현 중 정해지지 않은 문제를 업계에서 통상 쓰는 방법으로 정하고 진행한 기록이다. 항목마다 **무엇을 / 왜 / 다른 선택지 / 다시 볼 조건**을 적는다.
상태: `임시결정`(구현했음, 사용자 검토 대기) · `제외`(지시서가 이번에 안 하기로 함, 구현 안 함) · `확인대기`(실서버에서 아직 확인 못 함).
확정된 결정은 여기가 아니라 [adr/](adr/) 에 있다.

## A. 구현 중 정한 임시 결정

### O-01 모델 파일은 `models/` 로 복사, 원본 유지 — `임시결정`
- **무엇을**: `Downloads\Qwen3.5-4B-Q5_K_M.gguf` 를 `/mnt/c/Tinker/models/` 로 **복사**했다 (원본은 그대로).
- **왜**: 지시서가 `models/` 폴더에 넣으라고 했고, 사용자 파일을 이동·삭제하는 건 되돌리기 어렵다. 지시서에 적힌 경로가 실제로 존재함을 확인하고 진행했다.
- **다른 선택지**: 이동(디스크 3GB 절약), 심볼릭 링크(NTFS/WSL 에서 불안정).
- **다시 볼 때**: 디스크가 부족하면 `Downloads` 쪽을 지운다 (사용자 판단).

### O-02 llama.cpp 설치 위치와 버전 — `임시결정` · 드라이버 업데이트로 **해결됨**
- **무엇을**: 최신 릴리스 **b11377** 의 Linux CUDA 12.8 빌드를 `~/llama.cpp/llama-b11377/`(WSL 홈, ext4)에 풀었다. 레포 밖이라 git 에 안 들어간다. 스크립트는 `LLAMA_DIR` 환경변수로 위치를 바꿀 수 있다.
- **문제**: 이 PC 의 NVIDIA 드라이버가 546.80(CUDA 12.3)이라 12.8 로 빌드된 커널을 못 읽어 `CUDA error: device kernel image is invalid` 로 죽었다. `GGML_CUDA_PDL=0` 우회도 실패. → 사용자가 드라이버를 업데이트하기로 함. 상세는 [worklog.md](worklog.md).
- **다른 선택지**: Windows CUDA 12.4 빌드를 WSL 에서 `.exe` 로 실행(예비로 `bin/cuda12.4/` 에 받아 둠), Vulkan 빌드(`bin/vulkan/`, 드라이버 무관·느릴 수 있음), 소스 빌드(CUDA toolkit 필요).
- **다시 볼 때**: ~~드라이버 업데이트 후 정상 동작하면 `bin/` 은 지워도 된다~~ → **지우지 않는다.** 2026-10-04 llama-server 를 Windows 에서 실행하기로 해서 `bin/cuda12.4/` 가 실행 파일이 됐다 ([ADR-0015](adr/0015-llama-server-on-windows.md)). 이 항목의 WSL 설치(`~/llama.cpp/`)는 대안으로 유지. `bin/vulkan/` 은 계속 예비.
- 추가: `libgomp1`(OpenMP)이 WSL 에 없어 sudo 없이 `.deb` 에서 라이브러리만 꺼내 같은 폴더에 넣었다. 시스템 패키지는 건드리지 않았다.

### O-03 `-ngl 99` (전 레이어 GPU 적재) — `임시결정` · 확인됨(VRAM 약 3.5GB)
- **무엇을**: 지시서의 옵션 목록에 GPU 적재 옵션이 없어서 `-ngl 99` 를 추가했다.
- **왜**: 이게 없으면 GPU 빌드여도 CPU 로 돌 수 있다. 4B Q5_K_M(약 3GB) + KV 캐시(q8_0, 8192)는 6GB 에 들어갈 것으로 본다.
- **다른 선택지**: llama.cpp 의 `--fit` 자동 조정에 맡김(기본 on 인 것으로 보임), 레이어 수 직접 지정.
- **다시 볼 때**: VRAM 부족 에러가 나거나 다른 프로그램(게임 등)과 GPU 를 같이 쓸 때. 실제 VRAM 사용량은 worklog 에 적는다.

### O-04 샘플링 파라미터 위치 — `임시결정`
→ [ADR-0003](adr/0003-sampling-params-in-client.md). 값은 확정, 위치(클라이언트가 요청마다 전송)만 임시.

### O-05 서비스 예외 계층과 HTTP 상태 매핑 — `임시결정`
- **무엇을**: 서비스가 `LLMConnectionError → ChatUnavailableError → 503`, 그 외 `LLMError → ChatFailedError → 502` 로 한 칸씩 변환해 올린다. 라우터는 `llm` 모듈을 import 하지 않는다.
- **왜**: "레이어 건너뛰기 금지"([ADR-0004](adr/0004-layered-architecture.md))를 지키려면 프레젠테이션이 인프라 예외를 직접 잡으면 안 된다. 503/502 는 "상위 서버 문제"를 나타내는 통상적 상태 코드다.
- **다른 선택지**: 라우터가 `llm.exceptions` 를 직접 잡음(코드는 줄지만 레이어 건너뜀), 전역 exception handler(main.py).
- **다시 볼 때**: 오류 종류가 늘어 예외 클래스가 많아지면 전역 handler 로 모으는 걸 검토.

### O-10 빈 문자열·공백 질문 — `임시결정`
- **무엇을**: `query` 가 `""` 이면 422, **공백만 있는 문자열은 그대로 통과**시킨다.
- **왜**: "코드에 판단을 넣지 않는다"([ADR-0013](adr/0013-no-judgment-in-code.md)). 빈 문자열은 형식 문제(`min_length=1`)지만 공백이 의미 있는지는 판단이다.
- **다른 선택지**: 공백만 있어도 422, 최대 길이 제한.
- **다시 볼 때**: 공백 질문이 LLM 에서 이상 응답을 만들면.

### O-11 타임아웃 값 — `임시결정`
- **무엇을**: 서버→llama-server 120초(`LLM_TIMEOUT`), CLI→서버 150초. 읽기 타임아웃도 `LLMConnectionError` 로 묶는다.
- **왜**: 스트리밍 없이 전체 응답을 기다리므로 넉넉히 잡았다. CLI 가 서버보다 길어야 서버가 먼저 503 을 줄 수 있다. 임계값 근거는 실측이 아니라 **임의값**이다.
- **다시 볼 때**: 실제 응답 시간을 worklog 에 기록한 뒤 조정. 타임아웃과 연결 실패를 구분해야 하면 예외를 나눈다.

### O-12 `.env` 는 커밋하지 않는다 — `임시결정`
- 처음엔 비밀 값이 없어서 커밋하려 했으나, 사용자 지시로 `.gitignore` 에 넣었다. 코드에 기본값이 있어서 `.env` 없이도 동작한다(`LLM_BASE_URL`, `APP_HOST`, `APP_PORT`).
- **다시 볼 때**: 다른 PC 에서 설정 항목을 알아야 하면 `.env.example` 을 둔다.

### O-13 Python 3.12, 프로젝트 안 `.venv` — `임시결정`
- `uv` 가 Python 3.12.14 를 골랐다(시스템은 3.14 도 있음). `.venv/` 는 `/mnt/c`(NTFS) 위라 느릴 수 있다. 의존성 버전은 `requirements.txt` 에 고정.
- **다시 볼 때**: 설치·실행이 체감으로 느리면 venv 를 WSL 홈으로 옮긴다.

### O-14 LLM 클라이언트 싱글턴, 이력은 모듈 전역 — `임시결정`
- `get_llm_client()` 가 프로세스당 `AsyncClient` 하나를 만들어 공유하고 lifespan 종료 때 닫는다. 이력 리스트는 `chat/service.py` 모듈 전역이며 요청마다 만드는 `ChatService` 가 이를 공유한다.
- **왜**: "인메모리 리스트 하나"(ADR-0008)와 "클라이언트는 Depends 주입"(ADR-0010)을 동시에 만족하는 가장 짧은 구성.
- **다른 선택지**: `ChatService` 자체를 싱글턴(주입한 클라이언트가 고정돼 테스트 교체가 번거롭다), `app.state` 에 보관.
- **다시 볼 때**: 워커가 여러 개가 되거나 이력을 영속화할 때.

### O-15 CLI 동작 — `임시결정`
- 종료는 `/exit` 또는 Ctrl+D(Ctrl+C 도 종료). 빈 입력은 서버에 안 보내고 건너뛴다. 서버 오류가 나도 CLI 는 종료하지 않고 다음 입력을 받는다.
- **다른 선택지**: `exit`/`quit` 문자열(대화 내용과 겹칠 수 있어서 `/` 접두사로 구분).

### O-16 테스트 구성 — `임시결정`
- `pytest.ini` 를 두고 `integration` 마커는 기본 제외. 상세는 [testing.md](testing.md).
- 지시서 디렉토리 구조에는 `pytest.ini` 가 없지만 `pythonpath = .` 설정이 필요해서 추가했다.

### O-17 디렉토리 구조에 없던 것 추가 — `임시결정`
- `scripts/llama-server-moe.ps1`(Windows 서버 실행, 현재), `scripts/llama-server.sh`(WSL 서버 실행, 대안), `bin/`(Windows 바이너리, 현재 llama-server 실행용, git 제외), `models/`(git 제외), `pytest.ini`, `README.md`, `.gitignore`. 지시서가 "임의로 바꾸지 말 것"을 확정된 *결정*에 한정했다고 보고 구조 파일만 더했다. 마음에 안 들면 알려 달라.

### O-19 thinking 이 안 섞이는지 — 확인됨
- `--reasoning off` 옵션은 존재하지만 **효과는 실서버에서 확인했다(2026-10-04, 혼입 없음).** 통합 테스트 `test_reply_has_no_thinking_content` 가 확인한다.

### O-20 `/mnt/c` 에서 모델 로딩 속도 — 확인됨(약 21초, 이동 불필요)
- WSL 에서 NTFS 의 3GB 파일을 읽는 첫 로딩이 느릴 수 있다. 실측 후 worklog 에 기록. 느리면 `~/models` 로 옮기는 것을 검토한다([ADR-0014](adr/0014-wsl-runtime-and-paths.md)).
- Windows 에서 실행하면([ADR-0015](adr/0015-llama-server-on-windows.md)) Windows 가 직접 읽어서 해당 없음 (실측 약 6초, 파일 캐시 영향 가능).

### O-21 WSL(FastAPI) → Windows(llama-server) 연결 방식 — `확인대기` · **사용자 결정 필요**
- **문제(실측 2026-10-04)**: 이 PC 의 WSL 은 기본 NAT 모드(`.wslconfig` 없음, 게이트웨이 `172.27.160.1`)다. Windows 에서 `bin\cuda12.4\llama-server.exe` 를 띄우면 Windows 쪽 `localhost:8080/health` 는 200 인데, **WSL 에서 `localhost:8080` 은 연결 거부, `172.27.160.1:8080` 은 타임아웃**이었다. 서버가 기본 `127.0.0.1` 에만 바인딩하고 NAT 모드의 WSL 에는 Windows 의 localhost 가 안 보인다. 그래서 지금은 FastAPI → Windows llama-server 호출이 `LLMConnectionError` → 503 이다.
- **선택지**
  1. **mirrored 네트워킹 (권장 후보)**: `%UserProfile%\.wslconfig` 에 `[wsl2]` / `networkingMode=mirrored` 를 넣고 PowerShell 에서 `wsl --shutdown` 후 재시작. WSL 과 Windows 가 localhost 를 공유해서 `LLM_BASE_URL=http://localhost:8080`(기본값) 그대로 되고 서버는 `127.0.0.1` 바인딩 그대로라 외부에 안 열린다. 단점: WSL 전체의 네트워크 설정이 바뀐다. Windows 11 22H2 이상 필요(WSL 2.7.14 는 지원). **이 PC 에서는 아직 안 해 봤다.**
  2. **NAT 유지 + 호스트 IP**: llama-server 를 `--host 0.0.0.0` 으로 띄우고 Windows 방화벽 인바운드 8080 허용, `LLM_BASE_URL=http://<게이트웨이 IP>:8080`. 단점: WSL 재시작마다 IP 가 바뀐다. 인증 없는 서버가 같은 네트워크에 열릴 수 있다(방화벽 규칙을 WSL 대역으로 좁혀야 함, O-09 와 같은 위험).
  3. WSL 대안으로 복귀(`scripts/llama-server.sh`): 연결 문제가 없다.
- **다시 볼 때**: 사용자가 방식을 고르면 새 ADR 로 확정하고 이 항목과 README 의 "미정" 표시를 지운다.

## B. 이번에 하지 않기로 한 것 (구현하지 않음, 기록만) — `제외`

필요해 보여도 지시서에 따라 구현하지 않았다. 구현 중 "필요해 보인" 지점을 같이 적는다.

### O-06 컨텍스트 한도 처리
- 이력은 계속 쌓이고 `-c 8192` 를 넘으면 llama-server 가 오류를 내거나 앞부분을 잘라낼 수 있다(버전에 따라 다름). 지금은 **서버가 주는 HTTP 오류가 `LLMResponseError`→502 로 올라올 뿐**이다.
- 나중에 볼 방식: 오래된 턴 삭제, 요약, 토큰 수 계산. 어떤 기준으로 자를지는 판단이므로 사람이 정한다.

### O-07 동시 요청과 이력
- 두 요청이 동시에 오면 둘 다 같은 이력을 읽고 각자 뒤에 붙여서 순서가 섞일 수 있다. 사용자 1명·CLI 하나 전제라 방치. 필요하면 `asyncio.Lock`.

### O-08 스트리밍(SSE)
- 응답 전체를 기다리므로 긴 답변은 체감이 느리다. 나중에 `/chat` 을 SSE 로 바꿀 예정(ADR-0007). 바뀌는 곳: `LLMClient.chat`(스트림 반환), service, router, cli.

### O-09 영속화(DB) · 인증 · 미들웨어 · 헥사고날/Protocol · 툴 콜링
- 모두 이번 범위 밖. 서버가 `127.0.0.1` 에만 바인딩(기본)되어 있어 인증이 없어도 같은 PC 밖에서는 접근되지 않는다. 호스트를 `0.0.0.0` 으로 바꾸면 **인증 없이 외부에 열리니** 그 전에 인증을 검토해야 한다. llama-server 에도 같다: O-21 의 2번(`--host 0.0.0.0`)을 고르면 인증 없는 LLM 서버가 열린다.
