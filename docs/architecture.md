# 아키텍처

C4 모델의 Context → Container → Component 3단계를 Mermaid 로 그린다 (왜 이 방식인가: [documentation-guide.md](documentation-guide.md)).
용어는 현업 표기를 그대로 쓴다: 프레젠테이션 레이어 / 비즈니스 레이어(서비스) / 인프라 레이어(클라이언트).

## 1. Context — 시스템과 주변

```mermaid
flowchart LR
    user(["사용자 (1명)"])
    subgraph tinker["Tinker (개인 비서 AI)"]
        direction TB
        t["로컬 PC에서 도는 챗봇.<br/>대화 이력을 들고 LLM에 질문을 중계한다"]
    end
    llm[("llama-server<br/>Qwen3.6-35B-A3B 로컬 추론")]
    user -- "터미널에서 질문" --> tinker
    tinker -- "HTTP :8080 (WSL → Windows)" --> llm
```

외부 클라우드 API는 쓰지 않는다. 모든 통신은 이 PC 안에서 끝난다. 다만 Tinker(FastAPI·cli)는 WSL, llama-server 는 Windows 에서 돌아서 **WSL → Windows 경계를 넘는다** ([ADR-0015](adr/0015-llama-server-on-windows.md), 연결 방식은 미정: [O-21](open-items.md)).

## 2. Container — 실행되는 프로세스

```mermaid
flowchart LR
    user(["사용자"])
    cli["<b>cli.py</b><br/>터미널 챗 클라이언트<br/>(httpx)"]
    api["<b>FastAPI 서버</b> :8000<br/>POST /chat<br/>대화 이력 보관(메모리)"]
    subgraph wsl["WSL"]
        cli
        api
    end
    subgraph win["Windows"]
        llama["<b>llama-server</b> :8080<br/>llama.cpp + Qwen3.6-35B-A3B Q4_K_M<br/>(GPU + CPU MoE)"]
    end
    user --> cli
    cli -- "POST /chat<br/>{query} → {reply}" --> api
    api -- "POST /v1/chat/completions<br/>(OpenAI 호환 JSON)" --> llama
```

| 프로세스 | 실행 위치 | 시작 방법 | 상태 |
|---|---|---|---|
| llama-server | **Windows** (현재) | PowerShell 에서 `scripts\llama-server-moe.ps1` | 모델 로드 상태(VRAM·시스템 RAM) |
| llama-server (대안) | WSL | `scripts/llama-server.sh` | 같음. 둘 다 8080 이라 하나만 띄운다 |
| FastAPI 서버 | WSL | `python -m src.main` | **대화 이력**(메모리, 재시작하면 사라짐) |
| cli | WSL | `python cli.py` | 없음 (이력은 서버 소유) |

모델은 Qwen3.6-35B-A3B Q4_K_M GGUF 로 고정한다. `--cpu-moe` 로 전문가 가중치는 시스템 RAM 에 둔다 ([ADR-0017](adr/0017-model-qwen3-6-35b-a3b.md)). Windows·WSL 스크립트 모두 컨텍스트 `131072`, KV 캐시 q8_0 을 쓴다 ([ADR-0018](adr/0018-context-131072.md)).

## 3. Component — FastAPI 서버 내부 (레이어드 + 기능별 패키징)

```mermaid
flowchart TB
    subgraph pres["프레젠테이션 레이어"]
        router["chat/router.py<br/>요청 검증 · 서비스 호출 · 예외→HTTP 상태"]
        schemas["chat/schemas.py<br/>ChatRequest / ChatResponse"]
        main["main.py / config.py<br/>앱 조립 · 앱 설정"]
    end
    subgraph biz["비즈니스 레이어"]
        service["chat/service.py<br/>이력 보관 · 시스템 프롬프트 · 메시지 구성"]
    end
    subgraph infra["인프라 레이어"]
        client["llm/client.py<br/>형식 변환 · HTTP 호출 · 예외 변환"]
        cfg["llm/config.py<br/>base_url · 샘플링 값"]
        exc["llm/exceptions.py<br/>LLMConnectionError · LLMResponseError"]
    end
    ext[("llama-server")]
    router --> service
    router -.-> schemas
    service --> client
    client --> cfg
    client -.-> exc
    client -- "httpx" --> ext
```

### 레이어 규칙 (의존은 위 → 아래로만, 건너뛰기 금지)

| 레이어 | 하는 일 | 하면 안 되는 일 | 알고 있는 것 |
|---|---|---|---|
| 프레젠테이션 `router` | 요청 검증·변환, 응답/예외를 외부 형식(HTTP)으로 포장 | 비즈니스 로직 | 서비스만 (llm 모듈 모름) |
| 비즈니스 `service` | 규칙 판단과 처리 (이력, 프롬프트) | HTTP·외부 통신 방식 | 클라이언트의 `chat()` 과 `Message` |
| 인프라 `client` | 외부 통신, 형식 변환, 연결 정보, 외부 에러 → 내부 예외 | 비즈니스 판단 | httpx, llama-server API |

예외도 같은 규칙으로 한 칸씩만 올라간다:

```
httpx 예외 ─(client)→ LLMConnectionError / LLMResponseError ─(service)→ ChatUnavailableError / ChatFailedError ─(router)→ HTTP 503 / 502
```

### 패키징: 기능별 (Package by Feature)

- `chat/` — 채팅 기능의 router·schemas·service 가 한 폴더에 있다.
- `llm/` — LLM 호출 기능(client·config·exceptions).
- 기능이 늘면 `src/<기능>/` 을 추가한다. 레이어별 폴더(`routers/`, `services/`)로 나누지 않는다.

## 4. 요청 흐름 — `POST /chat`

```mermaid
sequenceDiagram
    autonumber
    actor U as 사용자
    participant C as cli.py
    participant R as router
    participant S as service
    participant L as llm client
    participant G as llama-server
    U->>C: 질문 입력
    C->>R: POST /chat {"query": "..."}
    R->>R: schemas 로 검증 (실패 시 422)
    R->>S: chat(query)
    S->>S: [시스템 프롬프트 + 이력 + 새 질문] 구성
    S->>L: chat(messages)
    L->>G: POST /v1/chat/completions (샘플링 값 포함)
    G-->>L: choices[0].message.content
    L-->>S: 답변 텍스트
    S->>S: 이력에 (질문, 답변) 추가
    S-->>R: 답변
    R-->>C: {"reply": "..."}
    C-->>U: 답변 출력
    Note over L,G: 연결 실패 → LLMConnectionError → 503<br/>이상 응답 → LLMResponseError → 502<br/>(실패한 턴은 이력에 남지 않는다)
```

## 5. 디렉토리

```
Tinker/
├── src/
│   ├── chat/          # 채팅 기능: router(프레젠테이션) schemas service(비즈니스)
│   ├── llm/           # LLM 호출 기능: client(인프라) config exceptions
│   ├── config.py      # 앱 공통 설정 (APP_*)
│   └── main.py        # FastAPI 앱 조립·실행
├── cli.py             # 터미널 클라이언트
├── tests/             # 레이어별 단위 테스트 + 앱 흐름 + integration(실서버)
├── scripts/           # llama-server 실행 스크립트: llama-server-moe.ps1(Windows, 현재) / llama-server.sh(WSL 대안)
├── models/            # 모델 파일, llama.cpp 캐시 (git 제외, Windows·WSL 이 같이 읽음)
├── bin/               # Windows 용 llama.cpp 바이너리 (git 제외, 현재 llama-server 실행에 사용)
├── docs/              # 이 문서들
├── .env               # 모듈별 설정 값 (git 제외, 기본값은 코드에 있음)
└── requirements.txt
```
