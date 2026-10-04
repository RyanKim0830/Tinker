# ADR-0016: 모델을 Qwen3.6-35B-A3B(Q4_K_M)로 변경하고 컨텍스트를 128k 로

- **Status**: Accepted — 사용자 확정 (2026-10-05, 2단계 작업 지시서의 '확정된 결정'). [ADR-0001](0001-local-llm-qwen3-5-4b.md) 을 대체한다.
- **Date**: 2026-10-05

## Context

툴 콜링과 검색 결과(스니펫) 읽기에는 4B 모델로는 부족하다. 또 검색 결과와 툴 호출이 이력에 전부 쌓이므로([ADR-0018](0018-react-loop-rules.md)) 8192 컨텍스트로는 몇 턴 못 간다. 환경은 그대로 RTX 4050 Laptop 6GB 이다.

## Decision

- 모델: **Qwen3.6-35B-A3B**, 양자화 **Q4_K_M** (`models/Qwen_Qwen3.6-35B-A3B-Q4_K_M.gguf`).
- 35B 는 6GB VRAM 에 안 들어가므로 MoE 전문가(expert) 가중치는 CPU(RAM)에 둔다: `--cpu-moe`. 나머지는 `-ngl 99` 로 GPU.
- 컨텍스트: **`-c 131072`** (128k). 두 실행 스크립트(`scripts/llama-server-moe.ps1`, `scripts/llama-server.sh`)에 반영했다.
- 실측(사용자 제공): 전용 VRAM 3.8/6.0GB, 공유 VRAM 0.2GB, RAM 54% 로 정상.
- 툴 콜링은 llama-server 의 jinja 채팅 템플릿에 의존한다. b11377 의 `--help` 에서 `--jinja` 가 **기본 enabled** 임을 확인해서 옵션을 따로 추가하지 않았다. 실서버에서 `tools` 요청에 `tool_calls` 가 오는 것도 확인했다([worklog](../worklog.md)).
- 나머지 옵션(`--cache-type-k/-v q8_0`, `--reasoning off`, 포트 8080)은 [ADR-0002](0002-inference-server-llama-server.md) 그대로다. (ADR-0002 의 `-c 8192` 만 이 ADR 이 덮어쓴다.)

## Considered Options

- Qwen3.5-4B 유지: 빠르고 VRAM 에 다 들어가지만 툴 호출 판단·한국어 답변 품질이 부족하다고 보았다 (사용자 판단).
- 컨텍스트 8192 유지: 검색 결과가 이력에 쌓이면 곧 넘친다. 한도 처리는 이번에 하지 않는다 (O-06).
- 전 레이어 GPU: 35B Q4_K_M 은 VRAM 에 안 들어간다.

## Consequences

- 속도가 4B(약 43 tok/s)보다 느리다. 이번 세션 실측: 생성 약 12~25 tok/s, 프롬프트 처리는 캐시가 없을 때 약 14~175 tok/s (측정 조건마다 크게 다름, [worklog](../worklog.md)).
- 첫 요청(프롬프트 캐시 없음)이 느리다. 그래서 CLI 타임아웃을 450초로 늘렸다.
- 샘플링 값([ADR-0003](0003-sampling-params-in-client.md))은 Qwen3.5 모델 카드의 non-thinking 값 그대로다. **Qwen3.6 권장값은 확인하지 않았다** (open-items O-27).
- 128k 를 끝까지 채웠을 때의 속도·메모리는 확인하지 않았다.

## Revisit when

VRAM/RAM 사용량이 부족해지거나, 답변 속도가 불편하거나, 128k 근처까지 대화가 길어질 때(O-06).
