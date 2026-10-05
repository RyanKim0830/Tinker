"""대화 메시지 내부 형식 (공용).

llm(서버 통신)과 chat(대화 이력·툴 루프)이 함께 쓰는 형식이라 어느 한쪽 패키지에 두지 않고 src 바로 아래에 둔다.
HTTP·서버 JSON 형식은 모른다. 변환은 llm/client.py 가 맡는다.
"""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ToolCall:
    """LLM 이 요청한 툴 호출 한 건."""

    id: str  # 서버가 붙인 호출 식별자. 결과 메시지(role="tool")의 tool_call_id 와 짝을 이룬다.
    name: str
    arguments: str  # 서버가 준 JSON 문자열 원문. 파싱·검증은 이 형식을 쓰는 쪽(chat)의 일이다.


@dataclass(frozen=True)
class Message:
    """대화 한 줄. 서비스 레이어가 쓰는 내부 형식이며 HTTP 형식은 모른다."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    # role="assistant" 일 때만: 이 답에 포함된 툴 호출. 있으면 content 는 비어 있을 수 있다.
    tool_calls: tuple[ToolCall, ...] = ()
    # role="tool" 일 때만: 이 결과가 어느 ToolCall.id 에 대한 것인지.
    tool_call_id: str | None = None
