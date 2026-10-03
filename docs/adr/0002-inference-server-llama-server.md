# ADR-0002: 추론 엔진: llama.cpp llama-server + 실행 옵션

- **Status**: Accepted — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

모델([ADR-0001](0001-local-llm-qwen3-5-4b.md))을 HTTP 로 호출할 추론 서버가 필요하다. 개인 사용이라 설치·운영이 단순해야 한다.

## Decision

**llama.cpp 의 `llama-server`, 포트 8080**. 옵션: `-c 8192`, `--cache-type-k q8_0`, `--cache-type-v q8_0`, `--reasoning off`.
- `--reasoning off`: Qwen3.5 는 thinking 이 기본 ON 이라 서버 옵션으로 끈다.
- 옵션 이름은 llama.cpp 버전마다 바뀔 수 있으니 설치된 버전의 `--help` 로 확인한다. **b11377 에서 위 옵션 이름이 전부 그대로 존재함을 확인했다** (worklog 참고).
- 실행은 `scripts/llama-server.sh`.

## Considered Options

- Ollama 등 다른 서버: 옵션 제어(KV 캐시 양자화, reasoning)가 덜 직접적
- vLLM: 6GB VRAM·Windows 환경에 부담

## Consequences

- 서버 프로세스가 앱과 분리되어 따로 띄워야 한다.
- 최신 모델 아키텍처 지원을 위해 최신 빌드가 필요할 수 있다.
- 추가로 `-ngl 99`(전 레이어 GPU 적재)를 쓴다 → open-items O-03.

## Revisit when

llama.cpp 옵션 이름이 바뀌거나, 다른 서버로 옮길 이유(성능·기능)가 생기면. 클라이언트 쪽 교체 비용은 `llm/client.py` 한 파일이다.
