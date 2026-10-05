"""chat/dependencies.py 단위 테스트: 서비스는 요청마다 새로 만들지만 이력은 하나를 공유하는지 본다."""
from src.chat.dependencies import get_chat_service
from src.message import Message


class FakeLLM:
    """받은 messages 를 기록하고 "a1", "a2" 처럼 순서대로 답한다."""

    def __init__(self):
        self.calls: list[list[Message]] = []

    async def chat(self, messages: list[Message], tools: list[dict] | None = None) -> Message:
        self.calls.append(messages)
        return Message("assistant", f"a{len(self.calls)}")


class FakeSearch:
    async def search(self, query: str) -> str:
        return ""


async def test_history_is_shared_across_service_instances():
    """get_chat_service 는 요청마다 새 서비스를 만들지만 이력은 하나를 공유한다 (session_id 없음)."""
    llm = FakeLLM()
    first, second = get_chat_service(llm, FakeSearch()), get_chat_service(llm, FakeSearch())
    assert first is not second
    await first.chat("q1")
    await second.chat("q2")
    assert llm.calls[1][1:3] == [Message("user", "q1"), Message("assistant", "a1")]
