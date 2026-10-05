# ADR-0017: 로컬 LLM 모델을 Qwen3.6-35B-A3B Q4_K_M 으로 고정한다

- **Status**: Accepted
- **Date**: 2026-10-05

## Context

이전 모델 결정은 Qwen3.5-4B Q5_K_M ([ADR-0001](0001-local-llm-qwen3-5-4b.md)) 이었다. 사용자가 현재 모델을 Qwen3.6-35B-A3B 로 확정했다. RTX 4050 Laptop 의 VRAM 은 6GB 라 전문가 가중치를 포함한 전체 모델을 GPU 에 둘 수 없다.

## Decision

- ADR-0001 을 대체한다. 모델은 **Qwen3.6-35B-A3B, Q4_K_M GGUF** 로 고정한다.
- 기본 파일은 `models/Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf` 이다. `-ngl 99` 와 `--cpu-moe` 를 함께 사용해 전문가 가중치는 CPU(시스템 RAM)에 둔다.
- Windows·WSL 실행 스크립트의 옵션을 함께 유지한다. 컨텍스트 길이는 [ADR-0018](0018-context-131072.md) 을 따른다.
- `--reasoning off` 를 유지한다. 클라이언트의 기존 샘플링 4개를 공식 모델 카드의 non-thinking 권장값 `temperature=0.7`, `top_p=0.8`, `top_k=20`, `presence_penalty=1.5` 로 맞춘다. 출처: [Qwen 공식 모델 카드, Best Practices](https://huggingface.co/Qwen/Qwen3.6-35B-A3B#best-practices) (2026-10-05 확인).

## Considered Options

- Qwen3.5-4B 유지: 사용자가 현재 모델을 35B-A3B 로 확정했다.
- 전문가 가중치까지 GPU 에 적재: VRAM 6GB 에 전체 모델이 들어가지 않는다.
- 샘플링 값을 추측해서 변경: 공식 카드에서 확인한 값만 적용한다.

## Consequences

- 모델 설명·다이어그램·실행 스크립트가 같은 모델을 가리킨다.
- 시스템 RAM 도 모델 실행 자원으로 필요하다. 사용자 메모리 실측은 [worklog](../worklog.md) 에 기록한다.
- 이전 4B 모델의 로딩 시간·생성 속도 실측을 현재 모델의 성능으로 해석하지 않는다. 이번에는 실서버 생성 속도를 확인하지 않았다.

## Revisit when

사용자가 모델·양자화 방식을 변경하거나, RAM·응답 속도 제약 때문에 실행 방식을 다시 정할 때.
