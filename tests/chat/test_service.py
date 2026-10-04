"""chat/service.py 단위 테스트 (비즈니스 레이어).

LLMClient 를 가짜(FakeLLM)로 바꿔서, 서비스가 LLM 에 '무엇을 보내는지'와 이력을 어떻게 관리하는지만 본다.
HTTP 는 등장하지 않는다 (서비스는 HTTP 를 몰라야 한다).
"""
import pytest

from src.chat import service
from src.chat.service import (
    SYSTEM_PROMPT,
    ChatFailedError,
    ChatService,
    ChatUnavailableError,
    get_chat_service,
)
from src.message import Message
from src.llm.exceptions import LLMConnectionError, LLMResponseError


class FakeLLM:
    """정해진 답을 순서대로 돌려주고, 받은 messages 를 (복사 없이) 그대로 기록한다."""

    def __init__(self, *replies, error: Exception | None = None):
        self.replies = list(replies)
        self.error = error
        self.calls: list[list[Message]] = []

    async def chat(self, messages: list[Message], tools: list[dict] | None = None) -> Message:
        self.calls.append(messages)
        if self.error:
            raise self.error
        return Message("assistant", self.replies.pop(0))


def make_service(llm: FakeLLM) -> ChatService:
    return ChatService(llm, service._history)


def test_system_prompt_is_confirmed_text():
    assert SYSTEM_PROMPT == "너는 사용자의 개인 비서다. 한국어로 짧게 답한다."


async def test_first_call_sends_system_prompt_and_query():
    llm = FakeLLM("안녕하세요.")
    reply = await make_service(llm).chat("안녕")
    assert reply == "안녕하세요."
    assert llm.calls[0] == [Message("system", SYSTEM_PROMPT), Message("user", "안녕")]


async def test_second_call_includes_first_exchange():
    llm = FakeLLM("반가워요 철수님.", "철수입니다.")
    svc = make_service(llm)
    await svc.chat("내 이름은 철수야")
    await svc.chat("내 이름이 뭐지?")
    assert llm.calls[1] == [
        Message("system", SYSTEM_PROMPT),
        Message("user", "내 이름은 철수야"),
        Message("assistant", "반가워요 철수님."),
        Message("user", "내 이름이 뭐지?"),
    ]


async def test_history_keeps_growing_in_order():
    llm = FakeLLM("a1", "a2", "a3")
    svc = make_service(llm)
    for q in ("q1", "q2", "q3"):
        await svc.chat(q)
    assert service._history == [
        Message("user", "q1"), Message("assistant", "a1"),
        Message("user", "q2"), Message("assistant", "a2"),
        Message("user", "q3"), Message("assistant", "a3"),
    ]


async def test_system_prompt_is_not_stored_and_not_duplicated():
    llm = FakeLLM("a1", "a2")
    svc = make_service(llm)
    await svc.chat("q1")
    await svc.chat("q2")
    assert all(m.role != "system" for m in service._history)
    assert sum(m.role == "system" for m in llm.calls[1]) == 1
    assert llm.calls[1][0].role == "system"  # 맨 앞


async def test_messages_sent_to_llm_are_a_snapshot():
    """LLM 에 넘긴 목록이 이후 이력 변경의 영향을 받으면 안 된다 (같은 리스트 객체를 공유하지 않는다)."""
    llm = FakeLLM("a1", "a2")
    svc = make_service(llm)
    await svc.chat("q1")
    first_call = list(llm.calls[0])
    await svc.chat("q2")
    assert llm.calls[0] == first_call


async def test_remembers_via_a_llm_that_only_knows_what_it_is_sent():
    """'기억'을 흉내 내는 LLM: 보낸 messages 안에 이름이 있을 때만 이름을 안다. 서비스가 이력을 안 보내면 실패한다."""

    class StatelessLLM:
        async def chat(self, messages, tools=None):
            said = " ".join(m.content for m in messages if m.role == "user")
            name = "철수" if "철수" in said and messages[-1].content == "내 이름이 뭐지?" else "모르겠어요"
            return Message("assistant", name)

    svc = ChatService(StatelessLLM(), service._history)
    await svc.chat("내 이름은 철수야")
    assert await svc.chat("내 이름이 뭐지?") == "철수"


async def test_connection_failure_becomes_unavailable_error():
    cause = LLMConnectionError("down")
    with pytest.raises(ChatUnavailableError) as info:
        await make_service(FakeLLM(error=cause)).chat("안녕")
    assert info.value.__cause__ is cause


async def test_bad_response_becomes_failed_error():
    cause = LLMResponseError("HTTP 500")
    with pytest.raises(ChatFailedError) as info:
        await make_service(FakeLLM(error=cause)).chat("안녕")
    assert info.value.__cause__ is cause
    assert not isinstance(info.value, ChatUnavailableError)  # 둘은 구분된다


async def test_failed_turn_is_not_saved_to_history():
    llm = FakeLLM("정상 답")
    svc = make_service(llm)
    llm.error = LLMConnectionError("down")
    with pytest.raises(ChatUnavailableError):
        await svc.chat("실패할 질문")
    assert service._history == []

    llm.error = None  # 서버가 살아났다
    await svc.chat("다음 질문")
    assert llm.calls[-1] == [Message("system", SYSTEM_PROMPT), Message("user", "다음 질문")]


async def test_unexpected_exception_is_not_swallowed():
    """llm 예외가 아닌 에러(버그 등)는 서비스 예외로 위장하지 않고 그대로 올라온다."""
    with pytest.raises(RuntimeError):
        await make_service(FakeLLM(error=RuntimeError("bug"))).chat("안녕")
    assert service._history == []


async def test_history_is_shared_across_service_instances():
    """get_chat_service 는 요청마다 새 서비스를 만들지만 이력은 하나를 공유한다 (session_id 없음)."""
    llm = FakeLLM("a1", "a2")
    await get_chat_service(llm).chat("q1")
    await get_chat_service(llm).chat("q2")
    assert llm.calls[1][1:3] == [Message("user", "q1"), Message("assistant", "a1")]
