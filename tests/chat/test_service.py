"""chat/service.py 단위 테스트 (비즈니스 레이어).

LLMClient·SearchService 를 가짜(FakeLLM, FakeSearch)로 바꿔서, 서비스가 LLM 에 '무엇을 보내는지', 툴 콜링 루프가
어떻게 도는지, 이력을 어떻게 관리하는지만 본다. HTTP 는 등장하지 않는다 (서비스는 HTTP 를 몰라야 한다).
"""
import logging
from datetime import date

import pytest
from pydantic import ValidationError

from src.chat import dependencies, tools
from src.chat.config import ChatSettings
from src.chat.exceptions import ChatFailedError, ChatUnavailableError
from src.chat.service import (
    BASE_PROMPT,
    SEARCH_PROMPT,
    ChatService,
    build_system_prompt,
)
from src.llm.exceptions import LLMConnectionError, LLMResponseError
from src.message import Message, ToolCall
from src.search.exceptions import SearchConnectionError

TODAY = date(2026, 10, 5)
SYSTEM = Message("system", build_system_prompt(TODAY))
SEARCH_TEXT = "[1] 서울 날씨 (http://w)\n서울 맑음, 19도"


class FakeLLM:
    """정해진 답(Message 또는 str)을 순서대로 돌려주고, 받은 messages·tools 를 기록한다.

    replies 항목이 예외면 그 차례에 던진다. error 는 모든 호출에 적용된다.
    """

    def __init__(self, *replies, error: Exception | None = None):
        self.replies = list(replies)
        self.error = error
        self.calls: list[list[Message]] = []
        self.tools: list[list[dict] | None] = []

    async def chat(self, messages: list[Message], tools: list[dict] | None = None) -> Message:
        self.calls.append(messages)
        self.tools.append(tools)
        if self.error:
            raise self.error
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return Message("assistant", reply) if isinstance(reply, str) else reply


class FakeSearch:
    """SearchService 대역. 질의를 기록하고 정해 둔 문자열을 돌려주거나 예외를 던진다."""

    def __init__(self, result: str = SEARCH_TEXT, error: Exception | None = None):
        self.result, self.error = result, error
        self.queries: list[str] = []

    async def search(self, query: str) -> str:
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.result


def make_service(llm, search: FakeSearch | None = None, max_rounds: int = 2) -> ChatService:
    return ChatService(
        llm, search or FakeSearch(), dependencies._history, ChatSettings(_env_file=None, max_tool_rounds=max_rounds),
        today=lambda: TODAY,
    )


def tool_call(id_: str = "c1", query: str = "서울 날씨", name: str = "web_search", arguments: str | None = None) -> ToolCall:
    return ToolCall(id_, name, arguments if arguments is not None else f'{{"query": "{query}"}}')


def asks(*calls: ToolCall, content: str = "") -> Message:
    """툴 호출을 요청하는 assistant 응답."""
    return Message("assistant", content, tuple(calls))


def assert_tool_calls_are_paired(history: list[Message]) -> None:
    """이력의 불변식: assistant(tool_calls) 바로 뒤에 같은 id 순서의 tool 결과가 전부 이어진다."""
    for i, m in enumerate(history):
        if m.tool_calls:
            following = history[i + 1 : i + 1 + len(m.tool_calls)]
            assert [(f.role, f.tool_call_id) for f in following] == [("tool", tc.id) for tc in m.tool_calls]
        if m.role == "tool":  # 짝 없는 tool 결과도 없다
            owner = next(h for h in reversed(history[:i]) if h.role == "assistant")
            assert m.tool_call_id in [tc.id for tc in owner.tool_calls]


# ---------- 시스템 프롬프트 ----------

def test_system_prompt_is_base_plus_today_plus_search_rule():
    prompt = build_system_prompt(date(2026, 10, 5))
    assert prompt == f"{BASE_PROMPT} 오늘 날짜는 2026-10-05이다. {SEARCH_PROMPT}"
    assert BASE_PROMPT == "너는 Ai 에이전트 Tinker 이다. 사용자와 친한 사이며, 아재개그를 좋아한다."  # 기존 문구(main 의 Tinker 페르소나) 유지
    assert SEARCH_PROMPT == "검색 결과가 있으면 그것을 근거로 답한다."


async def test_system_prompt_uses_injected_date():
    llm = FakeLLM("a")
    svc = ChatService(llm, FakeSearch(), dependencies._history, ChatSettings(_env_file=None), today=lambda: date(2030, 1, 2))
    await svc.chat("q")
    assert "2030-01-02" in llm.calls[0][0].content


# ---------- 툴 없이 답하는 기본 대화 (기존 동작 유지) ----------

async def test_first_call_sends_system_prompt_and_query():
    llm = FakeLLM("안녕하세요.")
    reply = await make_service(llm).chat("안녕")
    assert reply == "안녕하세요."
    assert llm.calls[0] == [SYSTEM, Message("user", "안녕")]


async def test_tools_are_offered_on_first_call():
    llm = FakeLLM("답")
    await make_service(llm).chat("잡담")
    assert llm.tools == [tools.TOOLS]


async def test_chat_without_tool_calls_does_not_search():
    search = FakeSearch()
    await make_service(FakeLLM("안녕하세요."), search).chat("안녕")
    assert search.queries == []


async def test_second_call_includes_first_exchange():
    llm = FakeLLM("반가워요 철수님.", "철수입니다.")
    svc = make_service(llm)
    await svc.chat("내 이름은 철수야")
    await svc.chat("내 이름이 뭐지?")
    assert llm.calls[1] == [
        SYSTEM,
        Message("user", "내 이름은 철수야"),
        Message("assistant", "반가워요 철수님."),
        Message("user", "내 이름이 뭐지?"),
    ]


async def test_history_keeps_growing_in_order():
    llm = FakeLLM("a1", "a2", "a3")
    svc = make_service(llm)
    for q in ("q1", "q2", "q3"):
        await svc.chat(q)
    assert dependencies._history == [
        Message("user", "q1"), Message("assistant", "a1"),
        Message("user", "q2"), Message("assistant", "a2"),
        Message("user", "q3"), Message("assistant", "a3"),
    ]


async def test_system_prompt_is_not_stored_and_not_duplicated():
    llm = FakeLLM("a1", "a2")
    svc = make_service(llm)
    await svc.chat("q1")
    await svc.chat("q2")
    assert all(m.role != "system" for m in dependencies._history)
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

    svc = make_service(StatelessLLM())
    await svc.chat("내 이름은 철수야")
    assert await svc.chat("내 이름이 뭐지?") == "철수"


# ---------- 검색 성공: 툴 호출 → 실행 → 결과를 붙여 다시 호출 ----------

async def test_search_flow_runs_tool_and_answers_from_result():
    search = FakeSearch()
    llm = FakeLLM(asks(tool_call("c1", "서울 날씨")), "서울은 맑고 19도입니다.")
    reply = await make_service(llm, search).chat("오늘 서울 날씨 알려줘")

    assert reply == "서울은 맑고 19도입니다."
    assert search.queries == ["서울 날씨"]  # 검색어는 LLM 이 툴 인자로 만든 것 그대로
    # 두 번째 호출에는 assistant(tool_calls)와 tool 결과가 짝으로 붙는다
    assert llm.calls[1] == [
        SYSTEM,
        Message("user", "오늘 서울 날씨 알려줘"),
        asks(tool_call("c1", "서울 날씨")),
        Message("tool", SEARCH_TEXT, tool_call_id="c1"),
    ]


async def test_history_stores_whole_turn_in_order():
    llm = FakeLLM(asks(tool_call("c1", "서울 날씨"), content="검색해 볼게요."), "맑아요.")
    await make_service(llm).chat("서울 날씨?")
    assert dependencies._history == [
        Message("user", "서울 날씨?"),
        asks(tool_call("c1", "서울 날씨"), content="검색해 볼게요."),
        Message("tool", SEARCH_TEXT, tool_call_id="c1"),
        Message("assistant", "맑아요."),
    ]
    assert_tool_calls_are_paired(dependencies._history)


async def test_follow_up_question_sees_search_text_from_history():
    """후속 질문에서 검색 원문을 참조할 수 있어야 한다 (이력 전체 저장의 이유)."""
    llm = FakeLLM(asks(tool_call()), "맑아요.", "기온은 19도예요.")
    svc = make_service(llm)
    await svc.chat("서울 날씨?")
    await svc.chat("기온은?")

    third = llm.calls[2]
    assert Message("tool", SEARCH_TEXT, tool_call_id="c1") in third
    assert third[-1] == Message("user", "기온은?")
    assert llm.tools[2] == tools.TOOLS  # 후속 질문의 첫 왕복은 다시 툴을 쓸 수 있다
    assert_tool_calls_are_paired(third)


async def test_multiple_tool_calls_run_in_order_and_count_as_one_round():
    search = FakeSearch()
    llm = FakeLLM(asks(tool_call("c1", "서울 날씨"), tool_call("c2", "부산 날씨")), "둘 다 맑아요.")
    reply = await make_service(llm, search).chat("서울이랑 부산 날씨")

    assert search.queries == ["서울 날씨", "부산 날씨"]  # 순서대로 전부 실행
    assert len(llm.calls) == 2  # 호출 개수가 아니라 LLM 왕복으로 센다
    assert [(m.role, m.tool_call_id) for m in llm.calls[1][-2:]] == [("tool", "c1"), ("tool", "c2")]
    assert reply == "둘 다 맑아요."
    assert_tool_calls_are_paired(dependencies._history)


# ---------- 검색 실패는 예외가 아니라 tool 결과 문자열 ----------

async def test_search_failure_is_returned_to_llm_as_tool_result():
    search = FakeSearch(error=SearchConnectionError("down"))
    llm = FakeLLM(asks(tool_call()), "지금은 검색이 안 돼서 확인하지 못했어요.")
    reply = await make_service(llm, search).chat("서울 날씨?")

    assert reply == "지금은 검색이 안 돼서 확인하지 못했어요."
    tool_msg = llm.calls[1][-1]
    assert tool_msg.role == "tool" and tool_msg.tool_call_id == "c1" and tool_msg.content.startswith("검색 실패")
    assert_tool_calls_are_paired(dependencies._history)


async def test_search_with_no_results_is_returned_as_tool_result():
    search = FakeSearch("검색 결과가 없다.")
    llm = FakeLLM(asks(tool_call()), "찾지 못했어요.")
    assert await make_service(llm, search).chat("q") == "찾지 못했어요."
    assert llm.calls[1][-1].content == "검색 결과가 없다."


# ---------- 잘못된 툴 호출 3종: 에러 내용을 tool 결과로 돌려주고 왕복 횟수에 포함 ----------

@pytest.mark.parametrize(
    "bad, expected",
    [
        (tool_call(arguments="{not json"), "JSON 이 아니다"),
        (tool_call(arguments="{}"), "query"),
        (tool_call(name="get_weather"), "등록되지 않은 툴"),
    ],
    ids=["arguments-not-json", "no-query", "unregistered-tool"],
)
async def test_invalid_tool_call_returns_error_as_tool_result(bad, expected):
    search = FakeSearch()
    llm = FakeLLM(asks(bad), "검색이 안 됐어요.")
    reply = await make_service(llm, search).chat("q")

    assert reply == "검색이 안 됐어요."
    assert search.queries == []  # 실행되지 않았다
    tool_msg = llm.calls[1][-1]
    assert (tool_msg.role, tool_msg.tool_call_id) == ("tool", "c1")
    assert expected in tool_msg.content
    assert_tool_calls_are_paired(dependencies._history)


async def test_invalid_tool_call_counts_as_a_round():
    """상한 2: 잘못된 호출이 첫 왕복을 썼으므로 두 번째 호출은 tools 없이 간다 (다시 시도할 수 없다)."""
    llm = FakeLLM(asks(tool_call(arguments="{not json")), "답")
    await make_service(llm).chat("q")
    assert llm.tools == [tools.TOOLS, None]


async def test_llm_can_retry_after_invalid_call_when_rounds_remain():
    search = FakeSearch()
    llm = FakeLLM(asks(tool_call("c1", arguments="{not json")), asks(tool_call("c2", "서울 날씨")), "맑아요.")
    reply = await make_service(llm, search, max_rounds=3).chat("q")

    assert reply == "맑아요."
    assert search.queries == ["서울 날씨"]
    assert llm.tools == [tools.TOOLS, tools.TOOLS, None]
    assert_tool_calls_are_paired(dependencies._history)


# ---------- 상한: 마지막 왕복은 tools 없이 ----------

async def test_last_round_is_sent_without_tools():
    llm = FakeLLM(asks(tool_call()), "검색 결과 기준으로 답")
    await make_service(llm, max_rounds=2).chat("q")
    assert llm.tools == [tools.TOOLS, None]


async def test_llm_is_never_called_more_than_the_limit():
    llm = FakeLLM(asks(tool_call("c1")), asks(tool_call("c2")), "끝", "쓰이지 않는 답")
    await make_service(llm, max_rounds=3).chat("q")
    assert len(llm.calls) == 3  # 모델이 4번째 답을 준비해 뒀어도 세 번째에서 끝난다
    assert llm.tools == [tools.TOOLS, tools.TOOLS, None]


@pytest.mark.parametrize("limit", [1, 2, 3, 5])
async def test_limit_follows_setting(limit):
    # 모델이 계속 툴만 부르려 해도 limit 번째 호출은 tools=None 이고 거기서 끝난다
    replies = [asks(tool_call(f"c{i}")) for i in range(limit - 1)] + ["최종"]
    llm = FakeLLM(*replies)
    assert await make_service(llm, max_rounds=limit).chat("q") == "최종"
    assert len(llm.calls) == limit
    assert llm.tools == [tools.TOOLS] * (limit - 1) + [None]


async def test_limit_one_never_offers_tools():
    llm = FakeLLM("바로 답")
    search = FakeSearch()
    assert await make_service(llm, search, max_rounds=1).chat("q") == "바로 답"
    assert llm.tools == [None] and search.queries == []


async def test_tool_calls_in_last_round_are_ignored_and_not_stored():
    """tools 를 안 줬는데 tool_calls 가 오면 실행하지 않는다. 짝 없는 호출이 이력에 남으면 안 된다."""
    llm = FakeLLM(asks(tool_call("c1")), asks(tool_call("c2"), content="그냥 답"))
    search = FakeSearch()
    reply = await make_service(llm, search).chat("q")

    assert reply == "그냥 답"
    assert search.queries == ["서울 날씨"]  # c1 만 실행
    assert dependencies._history[-1] == Message("assistant", "그냥 답")
    assert_tool_calls_are_paired(dependencies._history)


# ---------- LLM 실패: 이력에 저장하지 않는다 ----------

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
    assert dependencies._history == []

    llm.error = None  # 서버가 살아났다
    await svc.chat("다음 질문")
    assert llm.calls[-1] == [SYSTEM, Message("user", "다음 질문")]


@pytest.mark.parametrize(
    "error, expected", [(LLMConnectionError("down"), ChatUnavailableError), (LLMResponseError("500"), ChatFailedError)]
)
async def test_llm_failure_after_tool_round_leaves_history_untouched(error, expected):
    """검색까지 마치고 두 번째 왕복에서 LLM 이 실패하면, 앞의 user·assistant(tool_calls)·tool 도 저장하지 않는다."""
    dependencies._history.extend([Message("user", "이전"), Message("assistant", "이전 답")])
    before = list(dependencies._history)
    llm = FakeLLM(asks(tool_call()), error)  # 첫 왕복은 정상(검색까지 실행), 두 번째 왕복에서 실패
    with pytest.raises(expected):
        await make_service(llm).chat("서울 날씨?")
    assert dependencies._history == before


async def test_unexpected_exception_is_not_swallowed():
    """llm 예외가 아닌 에러(버그 등)는 서비스 예외로 위장하지 않고 그대로 올라온다."""
    with pytest.raises(RuntimeError):
        await make_service(FakeLLM(error=RuntimeError("bug"))).chat("안녕")
    assert dependencies._history == []


async def test_unexpected_exception_in_tool_leaves_history_untouched():
    llm = FakeLLM(asks(tool_call()), "답")
    with pytest.raises(RuntimeError):
        await make_service(llm, FakeSearch(error=RuntimeError("bug"))).chat("q")
    assert dependencies._history == []


# ---------- 빈 답 · 누출 · 로그 ----------

async def test_empty_final_content_returns_empty_string_and_logs(caplog):
    llm = FakeLLM("")
    with caplog.at_level(logging.WARNING, logger="src.chat.service"):
        reply = await make_service(llm).chat("q")
    assert reply == ""
    assert "비어 있다" in caplog.text
    assert dependencies._history[-1] == Message("assistant", "")  # 있는 그대로 저장


async def test_empty_final_content_after_search_returns_empty_string():
    llm = FakeLLM(asks(tool_call()), "")
    assert await make_service(llm).chat("q") == ""


async def test_leaked_tool_call_text_is_returned_as_is_and_logged_raw(caplog):
    """서버 파싱 실패로 툴 호출 텍스트가 content 에 새어 나와도 감지하지 않는다. 원문만 로그에 남긴다."""
    leaked = '<tool_call>{"name": "web_search", "arguments": {"query": "x"}}</tool_call>'
    search = FakeSearch()
    with caplog.at_level(logging.INFO, logger="src.chat.service"):
        reply = await make_service(FakeLLM(leaked), search).chat("q")
    assert reply == leaked and search.queries == []
    assert leaked in caplog.text


async def test_each_round_logs_raw_content_and_tool_calls(caplog):
    llm = FakeLLM(asks(tool_call("c1", "서울 날씨"), content="검색할게요"), "최종 답")
    with caplog.at_level(logging.INFO, logger="src.chat.service"):
        await make_service(llm).chat("q")
    text = caplog.text
    assert "round 1/2" in text and "검색할게요" in text and "서울 날씨" in text
    assert "round 2/2" in text and "최종 답" in text


# ---------- 설정 ----------

def test_settings_validation_rejects_less_than_one_round():
    with pytest.raises(ValidationError):
        ChatSettings(_env_file=None, max_tool_rounds=0)
