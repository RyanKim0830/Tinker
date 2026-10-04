"""대화 메시지 내부 형식 (공용).

llm(서버 통신)과 chat(대화 이력)이 함께 쓰는 형식이라 어느 한쪽 패키지에 두지 않고 src 바로 아래에 둔다.
HTTP·서버 JSON 형식은 모른다. 변환은 llm/client.py 가 맡는다.
"""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Message:
    """대화 한 줄. 서비스 레이어가 쓰는 내부 형식이며 HTTP 형식은 모른다."""

    role: Literal["system", "user", "assistant"]
    content: str
