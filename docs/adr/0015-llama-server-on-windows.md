# ADR-0015: 실행 환경: llama-server 는 Windows 에서, FastAPI 는 WSL 에서 (WSL 실행은 대안으로 보존)

- **Status**: Accepted — 사용자 확정 (2026-10-04, 대화에서 지시). [ADR-0014](0014-wsl-runtime-and-paths.md) 의 "llama-server 를 WSL 에서 실행" 부분을 대체한다.
- **Date**: 2026-10-04

## Context

[ADR-0014](0014-wsl-runtime-and-paths.md) 는 llama-server 를 WSL 에서 실행하기로 했다. 현재로서는 llama-server 를 Windows 에서 띄우기로 한다. FastAPI 서버와 `cli.py` 는 그대로 WSL 에서 연다. WSL 에서 열던 방식은 지우지 않고 필요하면 되돌릴 수 있게 남긴다.

## Decision

| 프로세스 | 실행 위치 | 방법 |
|---|---|---|
| llama-server | **Windows** (현재 기본) | `scripts\llama-server-moe.ps1` → `bin\cuda12.4\llama-server.exe` (PowerShell) |
| FastAPI 서버, `cli.py`, 테스트 | **WSL** (변함없음) | `.venv/bin/python -m src.main` 등 |

- Windows 에서는 경로가 Windows 형식이다: 모델 `C:\Tinker\models\...`, `LLAMA_CACHE=C:\Tinker\models`. 같은 `models/` 폴더를 WSL 은 `/mnt/c/Tinker/models` 로 본다. ADR-0014 의 "모델은 `models/` 폴더, 캐시도 같은 폴더, git 제외"는 그대로 유효하다.
- 옵션은 ADR-0002 와 같다 (`-c 8192`, `--cache-type-k/-v q8_0`, `--reasoning off`, `-ngl 99`, 포트 8080). `bin/cuda12.4/llama-server.exe` 의 빌드는 WSL 쪽과 같은 **b11377** 이고 위 옵션 이름이 모두 존재함을 확인했다.
- **WSL 실행은 대안으로 보존**한다. `scripts/llama-server.sh`, `~/llama.cpp/llama-b11377/` 는 그대로 두고, README 에 "WSL 에서 실행" 블록으로 남긴다. 전환은 아래 두 가지뿐이다.
  1. 어느 쪽 서버를 띄울지 (Windows 의 exe / WSL 의 `scripts/llama-server.sh`). **둘 다 8080 이므로 동시에 띄우지 않는다.**
  2. FastAPI 가 보는 주소 `LLM_BASE_URL` (`.env`). WSL 서버면 `http://localhost:8080`, Windows 서버면 연결 방식에 따라 다르다 (아래, O-21).
- 코드는 바꾸지 않았다. `src/llm/config.py` 의 기본값 `http://localhost:8080` 이 그대로다.

## Considered Options

- WSL 에서 계속 실행 (ADR-0014): 그대로도 동작한다 (2026-10-04 실측, 로딩 약 21초). 대안으로 남긴다.
- Windows 로 완전히 옮기고 `scripts/llama-server.sh` 삭제: 되돌리는 비용이 생겨서 안 한다.
- FastAPI 까지 Windows 로: 지시가 아니고, 개발 환경(`.venv`, pytest)이 WSL 이라 안 한다.

## Consequences

- **WSL → Windows 연결이 아직 안 된다.** 실측(2026-10-04, 이 PC 는 WSL2 기본 NAT 모드, `.wslconfig` 없음): Windows 에서 서버를 띄우고 Windows 쪽 `localhost:8080/health` 는 200, **WSL 에서 `localhost:8080` 은 연결 거부, 게이트웨이 IP(`172.27.160.1:8080`)는 타임아웃**이다. llama-server 가 기본으로 `127.0.0.1` 에만 바인딩하고 NAT 모드의 WSL 에는 Windows 의 localhost 가 보이지 않기 때문이다. 해결 방식은 사용자 결정이 필요해서 [open-items O-21](../open-items.md) 에 정리했다. 결정 전까지 FastAPI → Windows llama-server 는 연결되지 않는다.
- 이 PC 에서 Windows 의 `models/` 를 직접 읽으므로 NTFS-over-WSL 로딩 지연(O-20)이 사라진다 (실측 로딩 약 6초. 파일 캐시 영향 가능, WSL 첫 실행은 약 21초).
- GPU 는 같은 RTX 4050 6GB, VRAM 약 3.5GB 로 WSL 과 같다 (Qwen3.5-4B Q5_K_M 기준).
- `bin/` 은 더 이상 "예비용"이 아니다. 지우면 안 된다 (O-02 갱신).
- llama.cpp 를 업데이트하면 **두 곳(`bin/`, `~/llama.cpp/`)** 을 맞춰야 한다. WSL 대안을 안 쓰면 WSL 쪽은 방치해도 된다.
- 실행 스크립트가 두 개다: Windows 용 `scripts/llama-server-moe.ps1`, WSL 용 `scripts/llama-server.sh`. 옵션(모델 기본값, `--cpu-moe` 등)이 같아야 하니 **한쪽을 고치면 다른 쪽도 고친다.**

## Revisit when

- ~~O-21(연결 방식)이 결정되면 이 ADR 의 Consequences 첫 항목을 새 ADR 로 확정한다.~~ → [ADR-0020](0020-wsl-windows-mirrored-networking.md) 에서 mirrored 네트워킹으로 확정됨 (2026-10-05).
- WSL 대안을 쓸 일이 없어지면 `scripts/llama-server.sh` 와 `~/llama.cpp/` 정리를 검토.
