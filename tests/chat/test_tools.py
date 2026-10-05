"""chat/tools.py 단위 테스트 (비즈니스 레이어).

가짜 SearchService 로 툴 정의와 run_tool 의 동작을 본다. HTTP 는 등장하지 않는다.
핵심 약속: 툴 실행의 실패(잘못된 호출, 검색 실패)는 예외가 아니라 '결과 문자열'로 돌아온다.
"""
import logging

import pytest

from src.chat import tools
from src.chat.config import ChatSettings
from src.message import ToolCall
from src.search.exceptions import SearchConnectionError, SearchResponseError
from src.search.service import NO_RESULTS


class FakeSearch:
    """SearchService 대역. 정해 둔 문자열을 돌려주거나 예외를 던진다."""

    def __init__(self, result: str = "[1] 제목 (http://u)\n내용", error: Exception | None = None):
        self.result, self.error = result, error
        self.queries: list[str] = []

    async def search(self, query: str) -> str:
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.result


def call(arguments: str, name: str = "web_search") -> ToolCall:
    return ToolCall("c1", name, arguments)


# ---------- 툴 정의 ----------

def test_web_search_is_the_only_tool_and_requires_query():
    assert [t["function"]["name"] for t in tools.TOOLS] == ["web_search"]
    fn = tools.TOOLS[0]["function"]
    assert tools.TOOLS[0]["type"] == "function"
    assert fn["description"]
    assert fn["parameters"]["properties"]["query"]["type"] == "string"
    assert fn["parameters"]["required"] == ["query"]


def test_every_tool_definition_has_a_handler():
    assert {t["function"]["name"] for t in tools.TOOLS} == set(tools._HANDLERS)


# ---------- 정상 ----------

async def test_web_search_passes_query_and_returns_search_text():
    search = FakeSearch("[1] A (http://a)\n가")
    assert await tools.run_tool(call('{"query": "서울 날씨"}'), search) == "[1] A (http://a)\n가"
    assert search.queries == ["서울 날씨"]


async def test_no_results_message_is_passed_through():
    assert await tools.run_tool(call('{"query": "q"}'), FakeSearch(NO_RESULTS)) == NO_RESULTS


async def test_extra_arguments_are_ignored():
    search = FakeSearch()
    await tools.run_tool(call('{"query": "q", "limit": 3}'), search)
    assert search.queries == ["q"]


async def test_empty_query_is_not_judged():
    """코드에 판단을 넣지 않는다: 빈 검색어가 의미 있는지는 판단이므로 그대로 검색에 넘긴다."""
    search = FakeSearch()
    await tools.run_tool(call('{"query": ""}'), search)
    assert search.queries == [""]


# ---------- 잘못된 툴 호출: 예외가 아니라 문자열, 검색은 하지 않는다 ----------

async def test_unregistered_tool_name_returns_error_string():
    search = FakeSearch()
    out = await tools.run_tool(call('{"query": "q"}', name="get_weather"), search)
    assert "등록되지 않은 툴" in out and "get_weather" in out and "web_search" in out  # 쓸 수 있는 툴도 알려 준다
    assert search.queries == []


@pytest.mark.parametrize("arguments", ["{not json", "", "서울 날씨"], ids=["broken", "empty", "plain-text"])
async def test_arguments_not_json_returns_error_string(arguments):
    search = FakeSearch()
    out = await tools.run_tool(call(arguments), search)
    assert "JSON 이 아니다" in out
    assert search.queries == []


@pytest.mark.parametrize("arguments", ["[1, 2]", '"서울"', "null", "3"], ids=["array", "string", "null", "number"])
async def test_arguments_not_object_returns_error_string(arguments):
    search = FakeSearch()
    out = await tools.run_tool(call(arguments), search)
    assert "JSON 객체" in out
    assert search.queries == []


@pytest.mark.parametrize("arguments", ["{}", '{"q": "서울"}', '{"query": null}', '{"query": 123}', '{"query": ["a"]}'],
                         ids=["empty-object", "wrong-key", "null", "number", "list"])
async def test_missing_or_non_string_query_returns_error_string(arguments):
    search = FakeSearch()
    out = await tools.run_tool(call(arguments), search)
    assert "query" in out and out.startswith("오류")
    assert search.queries == []


# ---------- 검색 실패: 예외가 아니라 문자열 ----------

async def test_search_connection_error_becomes_string():
    out = await tools.run_tool(call('{"query": "q"}'), FakeSearch(error=SearchConnectionError("refused")))
    assert out.startswith("검색 실패") and "연결" in out


async def test_search_response_error_becomes_string():
    out = await tools.run_tool(call('{"query": "q"}'), FakeSearch(error=SearchResponseError("HTTP 500")))
    assert out.startswith("검색 실패") and "응답" in out


async def test_search_error_text_does_not_leak_internal_details():
    out = await tools.run_tool(call('{"query": "q"}'), FakeSearch(error=SearchConnectionError("http://localhost:8888 refused")))
    assert "localhost" not in out


async def test_unexpected_exception_is_not_hidden():
    """검색 예외(SearchError)만 문자열로 바꾼다. 코드 버그는 숨기지 않고 올린다."""
    with pytest.raises(RuntimeError):
        await tools.run_tool(call('{"query": "q"}'), FakeSearch(error=RuntimeError("bug")))


# ---------- 로그 ----------

async def test_call_and_generated_query_are_logged(caplog):
    with caplog.at_level(logging.INFO, logger="src.chat.tools"):
        await tools.run_tool(call('{"query": "서울 날씨"}'), FakeSearch())
    assert "web_search" in caplog.text and "서울 날씨" in caplog.text


# ---------- 설정 ----------

def test_chat_settings_default_and_env(monkeypatch):
    assert ChatSettings(_env_file=None).max_tool_rounds == 2
    monkeypatch.setenv("CHAT_MAX_TOOL_ROUNDS", "4")
    assert ChatSettings(_env_file=None).max_tool_rounds == 4


def test_chat_settings_rejects_zero_rounds():
    """0 이면 LLM 을 한 번도 안 부르는 설정이라 시작할 때 거절한다."""
    with pytest.raises(ValueError):
        ChatSettings(_env_file=None, max_tool_rounds=0)
