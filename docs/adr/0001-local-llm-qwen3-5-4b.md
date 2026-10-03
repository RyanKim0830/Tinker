# ADR-0001: 로컬 LLM 모델: Qwen3.5-4B (Unsloth GGUF Q5_K_M)

- **Status**: Accepted — 사용자 확정 (작업 지시서의 '확정된 결정')
- **Date**: 2026-10-03

## Context

개인 비서의 첫 기능으로 로컬에서 돌아가는 챗봇이 필요하다. 외부 클라우드 API는 쓰지 않는다. 환경은 Windows PC, GPU VRAM 6GB.

## Decision

모델은 **Qwen3.5-4B**, 파일은 **Unsloth GGUF `Q5_K_M`** (`unsloth/Qwen3.5-4B-GGUF`)를 쓴다. 파일은 사용자가 직접 받아 넣는다.

## Considered Options

- 더 낮은 양자화(예: Q4_K_M): VRAM·속도에 유리, 품질 손해
- 더 큰 모델(7~8B급): 6GB VRAM 에 KV 캐시까지 올리기 어렵다
- 클라우드 API: 요구사항에서 제외

## Consequences

- 파일 약 3.1GB. 4B 모델이라 6GB VRAM 에 전 레이어를 올릴 수 있다 ([ADR-0002](0002-inference-server-llama-server.md)).
- Qwen3.5 는 기본이 thinking ON 이라 서버 옵션으로 꺼야 한다.

## Revisit when

한국어 답변 품질이 부족하거나, VRAM 여유가 생기면(GPU 교체) 더 큰 모델/낮은 압축률로 바꿔 볼 만하다.
