# ADR-0014: 실행 환경: llama-server 를 WSL 에서 실행, 경로는 /mnt/c, 모델은 models/ 폴더

- **Status**: Accepted — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

개발 환경이 WSL 이라 Windows 경로(`C:\Users\User\Downloads\...`)를 WSL 프로세스가 직접 읽지 못한다. 모델과 캐시를 프로젝트 안에 모으고 싶다.

## Decision

- 경로는 WSL 이 읽는 형식(`/mnt/c/Tinker/models/...`)으로 가공한다 (`scripts/llama-server.sh` 가 `$ROOT` 기준으로 계산).
- 모델 파일은 `models/` 에 둔다. 원본 `Downloads/` 파일은 건드리지 않고 **복사**했다.
- `LLAMA_CACHE=models/` 로 llama.cpp 캐시도 같은 폴더를 쓴다. `models/` 는 git 제외.

## Considered Options

- Windows 용 llama-server.exe 를 WSL 에서 호출: 경로를 `wslpath -w` 로 바꿔야 한다. 예비용으로 `bin/` 에 받아 두었다

## Consequences

- `/mnt/c`(NTFS) 에서 모델을 읽어 첫 로딩이 느릴 수 있다 (O-20).
- 실제 설치 중 CUDA 드라이버 호환 문제가 있었다 → worklog.

## Revisit when

모델 로딩이 너무 느리면 WSL 내부 파일시스템(`~/`)으로 옮기는 것을 검토.
