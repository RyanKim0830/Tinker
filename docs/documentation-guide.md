# 문서화 방법 (조사 · 채택 · 이유)

몇 달 뒤 처음 보는 사람(미래의 나 포함)이 이 코드를 빠르게 읽을 수 있게 하려고 어떤 문서를 어떤 형식으로 두는지 정리한 문서다.

## 1. 조사 결과 (2026-10 웹 검색)

| 영역 | 통상적인 방법 | 특징 |
|---|---|---|
| 구조도 표기법 | **C4 모델** (Context → Container → Component → Code 4단계 확대) | 청중에 따라 확대 수준을 고른다. 표기가 단순해 UML 지식이 필요 없다 |
| 구조도 도구 | **Mermaid** / PlantUML(C4-PlantUML) / Structurizr DSL | 모두 텍스트로 관리(diagrams-as-code). Mermaid 는 GitHub Markdown 이 바로 렌더링한다. Mermaid 의 전용 C4 문법은 아직 experimental 이라고 문서에 명시돼 있다 |
| 설계 결정 기록 | **ADR** (Architecture Decision Record). 형식은 Nygard(Status·Context·Decision·Consequences) 또는 **MADR**(여기에 Considered Options·장단점 추가) | 결정 1개 = 파일 1개. 결정이 뒤집히면 지우지 않고 Status 만 바꾼다 |
| 문서 구조 | **arc42** (12개 절 템플릿), 필요한 절만 쓰는 축소 사용이 일반적 | "무엇을 어디에 쓰는지"의 목차 역할 |
| 문서 관리 방식 | **docs-as-code**: 코드와 같은 Git 레포, Markdown, PR/커밋으로 변경 이력 | 코드와 문서가 같이 바뀌어 어긋남이 적다 |
| README 구성 | 무엇인가 → 빠른 실행 → 구조 → 문서 링크 → 개발/테스트 | 첫 5분 안에 실행해 보는 것이 목적 |

참고: arc42/C4/ADR/docs-as-code 개요 ([Spryker](https://docs.spryker.com/docs/dg/dev/architecture/architecture-as-code)), ADR 형식 비교 ([MADR/Nygard 정리](https://hidekazu-konishi.com/entry/architecture_decision_records_templates_and_operations.html)), Mermaid C4 지원 상태 ([Mermaid](https://docsearch.algolia.com/mcp/docs/repo/mermaid-js/mermaid)).

## 2. 채택한 방법

| 항목 | 채택 | 위치 |
|---|---|---|
| 구조도 | **C4 모델 3단계(Context, Container, Component)** + 요청 흐름 시퀀스 다이어그램, **Mermaid** `flowchart`/`sequenceDiagram` 로 작성 | [architecture.md](architecture.md) |
| 설계 결정 기록 | **ADR, MADR 축약형** (Status / Context / Decision / Considered Options / Consequences / Revisit when) | [adr/](adr/) |
| 미결사항 | 임시 결정은 ADR 의 한 형태가 아니라 별도 목록으로 관리 (무엇을·왜·다른 선택지·다시 볼 조건) | [open-items.md](open-items.md) |
| 문서 목차 | arc42 를 **통째로 쓰지 않고** 필요한 부분만 대응시킨다: 1 소개→README, 5 구성요소→architecture.md, 9 결정→adr/, 11 리스크·부채→open-items.md | 아래 표 |
| 작업 기록 | 단계별 worklog (만든 것 / 확인 결과 / 문제와 해결) | [worklog.md](worklog.md) |
| 테스트 문서 | 테스트 전략·실행법·추가 규칙 | [testing.md](testing.md) |
| 관리 방식 | docs-as-code: 전부 Markdown, 레포 안, 코드와 같은 커밋 | `docs/` |
| 코드 설명 | 파일 맨 위 docstring(역할·소속 레이어), 핵심 부분에 주석 | `src/` |

## 3. 채택 이유

- **C4**: 이 프로젝트는 "누가 누구를 부르는가"(시스템 → 프로세스 → 레이어)가 이해의 핵심이라 확대 수준별 그림이 맞다. 4단계(Code)는 코드 자체가 대신하므로 그리지 않는다.
- **Mermaid**: 별도 도구·서버 없이 GitHub/VS Code 미리보기에서 렌더링되고 diff 로 변경이 보인다. PlantUML 은 Java/서버가 필요하고, Structurizr 는 이 규모에는 과하다. 전용 C4 문법은 experimental 이라 **일반 flowchart 로 C4 의 개념(경계·역할·관계 설명)만 따른다**.
- **ADR(MADR 축약)**: 요구사항이 "무엇을·왜·다른 선택지·다시 볼 조건"을 명시했는데 MADR 의 Considered Options 가 이를 그대로 담는다. `Revisit when` 은 요구사항에 맞춰 추가한 항목이다.
- **arc42 전체 미채택**: 12개 절은 팀·장기 시스템용이다. 1인 개인 시스템이라 과하다 (확장성·멀티테넌시를 기본으로 깔지 않는다는 원칙과 같은 이유).

## 4. 문서 지도

| 알고 싶은 것 | 볼 문서 |
|---|---|
| 이게 뭐고 어떻게 실행하나 | [../README.md](../README.md) |
| 코드가 어떻게 나뉘고 요청이 어떻게 흐르나 | [architecture.md](architecture.md) |
| 왜 이렇게 만들었나 | [adr/](adr/) (색인: [adr/README.md](adr/README.md)) |
| 아직 안 정했거나 임시로 정한 것 | [open-items.md](open-items.md) |
| 테스트 어떻게 돌리고 추가하나 | [testing.md](testing.md) |
| 지금까지 뭘 했고 뭐가 막혔나 | [worklog.md](worklog.md) |

## 5. 유지 규칙

- 결정이 바뀌면 ADR 을 지우거나 고치지 않고 **새 ADR 을 만들고 이전 것의 Status 를 `Superseded by ADR-xxxx` 로 바꾼다.**
- 임시로 정한 것은 코드에 넣는 순간 open-items.md 에 같이 적는다.
- 새 파일·레이어를 추가하면 architecture.md 의 다이어그램을 같은 커밋에서 고친다.
