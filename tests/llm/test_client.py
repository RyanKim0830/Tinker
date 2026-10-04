"""llm/client.py 단위 테스트 (인프라 레이어).

httpx.MockTransport 로 llama-server 를 흉내 낸다. 실제 서버는 필요 없다.
검증 대상: 요청 변환(내부 형식 → 서버 JSON, tools 전송), 응답 변환(content, tool_calls), 모든 실패 경로의 내부 예외 변환.
"""
import json
import logging
import socket

import httpx
import pytest

from src.llm import client as client_module
from src.llm.client import LLMClient
from src.llm.config import LLMSettings
from src.llm.exceptions import LLMConnectionError, LLMError, LLMResponseError
from src.message import Message, ToolCall

MESSAGES = [
    Message("system", "너는 비서다."),
    Message("user", "안녕"),
    Message("assistant", "안녕하세요."),
    Message("user", "이름이 뭐야?"),
]


def ok_body(content: str) -> dict:
    """llama-server(OpenAI 호환)의 정상 응답 형태."""
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def make_client(handler, **settings) -> LLMClient:
    """handler(request) -> httpx.Response 를 서버로 쓰는 클라이언트. .env 영향을 받지 않게 env_file 을 끈다."""
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LLMClient(http, LLMSettings(_env_file=None, **settings))


# ---------- 정상 경로 ----------

async def test_returns_assistant_content():
    c = make_client(lambda req: httpx.Response(200, json=ok_body("저는 비서입니다.")))
    assert await c.chat(MESSAGES) == Message("assistant", "저는 비서입니다.")


async def test_request_goes_to_chat_completions_endpoint():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["method"], seen["url"] = req.method, str(req.url)
        return httpx.Response(200, json=ok_body("ok"))

    await make_client(handler, base_url="http://example:9999").chat(MESSAGES)
    assert seen == {"method": "POST", "url": "http://example:9999/v1/chat/completions"}


async def test_request_payload_converts_messages_in_order():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=ok_body("ok"))

    await make_client(handler).chat(MESSAGES)
    assert seen["body"]["messages"] == [
        {"role": "system", "content": "너는 비서다."},
        {"role": "user", "content": "안녕"},
        {"role": "assistant", "content": "안녕하세요."},
        {"role": "user", "content": "이름이 뭐야?"},
    ]
    assert seen["body"]["stream"] is False  # 이번 단계는 스트리밍 없음


async def test_request_payload_has_default_sampling_params():
    """확정된 결정: Qwen3.5 non-thinking 일반 작업 권장값."""
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=ok_body("ok"))

    await make_client(handler).chat(MESSAGES)
    b = seen["body"]
    assert (b["temperature"], b["top_p"], b["top_k"], b["presence_penalty"]) == (0.7, 0.8, 20, 1.5)


async def test_sampling_params_follow_settings():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=ok_body("ok"))

    await make_client(handler, temperature=0.1, top_p=0.5, top_k=5, presence_penalty=0.0).chat(MESSAGES)
    b = seen["body"]
    assert (b["temperature"], b["top_p"], b["top_k"], b["presence_penalty"]) == (0.1, 0.5, 5, 0.0)


async def test_content_is_returned_untouched():
    """코드에 판단을 넣지 않는다: 내용을 제거·정리·추정하지 않고 그대로 돌려준다."""
    raw = "  <think>생각</think>\n답변  "
    c = make_client(lambda req: httpx.Response(200, json=ok_body(raw)))
    assert (await c.chat(MESSAGES)).content == raw


# ---------- 툴 콜링 ----------

TOOLS = [{"type": "function", "function": {"name": "web_search", "description": "웹 검색", "parameters": {"type": "object"}}}]


def tool_call_body(content, calls: list[dict]) -> dict:
    """llama-server 가 툴 호출을 줄 때의 응답 형태 (실서버에서 확인한 모양)."""
    return {
        "choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": content, "tool_calls": calls}}]
    }


def raw_call(id_: str, name: str, arguments) -> dict:
    return {"type": "function", "id": id_, "function": {"name": name, "arguments": arguments}}


async def test_tools_are_sent_when_given():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=ok_body("ok"))

    await make_client(handler).chat(MESSAGES, TOOLS)
    assert seen["body"]["tools"] == TOOLS


@pytest.mark.parametrize("tools", [None, []], ids=["none", "empty-list"])
async def test_tools_field_is_omitted_without_tools(tools):
    """상한 도달 시 '툴 없이' 부르는 경로. 빈 tools 도 보내지 않는다."""
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=ok_body("ok"))

    await make_client(handler).chat(MESSAGES, tools)
    assert "tools" not in seen["body"]


async def test_tool_calls_are_parsed_into_message():
    raw = tool_call_body("", [raw_call("c1", "web_search", '{"query":"서울 날씨"}')])
    reply = await make_client(lambda req: httpx.Response(200, json=raw)).chat(MESSAGES, TOOLS)
    assert reply == Message("assistant", "", (ToolCall("c1", "web_search", '{"query":"서울 날씨"}'),))


async def test_multiple_tool_calls_keep_server_order():
    raw = tool_call_body("", [raw_call("c1", "web_search", '{"query":"a"}'), raw_call("c2", "web_search", '{"query":"b"}')])
    reply = await make_client(lambda req: httpx.Response(200, json=raw)).chat(MESSAGES, TOOLS)
    assert [tc.id for tc in reply.tool_calls] == ["c1", "c2"]


async def test_null_content_with_tool_calls_becomes_empty_string():
    raw = tool_call_body(None, [raw_call("c1", "web_search", "{}")])
    reply = await make_client(lambda req: httpx.Response(200, json=raw)).chat(MESSAGES, TOOLS)
    assert reply.content == "" and len(reply.tool_calls) == 1


async def test_null_content_without_tool_calls_becomes_empty_string():
    """빈 답을 돌려주는 것까지가 클라이언트의 일이다. 어떻게 다룰지는 서비스가 정한다."""
    raw = {"choices": [{"message": {"role": "assistant", "content": None}}]}
    reply = await make_client(lambda req: httpx.Response(200, json=raw)).chat(MESSAGES)
    assert reply == Message("assistant", "")


@pytest.mark.parametrize("calls", [None, []], ids=["null", "empty-list"])
async def test_no_tool_calls_gives_empty_tuple(calls):
    raw = {"choices": [{"message": {"content": "답", "tool_calls": calls}}]}
    reply = await make_client(lambda req: httpx.Response(200, json=raw)).chat(MESSAGES)
    assert reply.tool_calls == ()


async def test_arguments_are_kept_as_raw_string_even_if_not_json():
    """arguments 가 JSON 인지는 클라이언트가 판단하지 않는다 (chat 이 잘못된 툴 호출로 처리)."""
    raw = tool_call_body("", [raw_call("c1", "web_search", "{not json")])
    reply = await make_client(lambda req: httpx.Response(200, json=raw)).chat(MESSAGES, TOOLS)
    assert reply.tool_calls[0].arguments == "{not json"


async def test_tool_messages_are_serialized_in_request():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=ok_body("ok"))

    msgs = [
        Message("user", "서울 날씨"),
        Message("assistant", "", (ToolCall("c1", "web_search", '{"query":"서울 날씨"}'),)),
        Message("tool", "[1] 날씨 (http://w)\n맑음", tool_call_id="c1"),
    ]
    await make_client(handler).chat(msgs, TOOLS)
    assert seen["body"]["messages"] == [
        {"role": "user", "content": "서울 날씨"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "web_search", "arguments": '{"query":"서울 날씨"}'}}],
        },
        {"role": "tool", "content": "[1] 날씨 (http://w)\n맑음", "tool_call_id": "c1"},
    ]


async def test_plain_messages_have_no_tool_fields():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(req.content)
        return httpx.Response(200, json=ok_body("ok"))

    await make_client(handler).chat([Message("user", "안녕")])
    assert seen["body"]["messages"] == [{"role": "user", "content": "안녕"}]


async def test_timings_and_finish_reason_are_logged(caplog):
    raw = {"choices": [{"finish_reason": "stop", "message": {"content": "ok"}}], "timings": {"predicted_per_second": 12.1}}
    with caplog.at_level(logging.INFO, logger="src.llm.client"):
        await make_client(lambda req: httpx.Response(200, json=raw)).chat(MESSAGES)
    assert "finish_reason=stop" in caplog.text and "predicted_per_second" in caplog.text


# ---------- 실패 경로: 전부 llm 전용 예외로 바뀌어야 한다 ----------

@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectError("refused"),
        httpx.ConnectTimeout("connect timeout"),
        httpx.ReadTimeout("read timeout"),
        httpx.RemoteProtocolError("server disconnected"),
    ],
)
async def test_transport_errors_become_connection_error(exc):
    def handler(req):
        raise exc

    with pytest.raises(LLMConnectionError) as info:
        await make_client(handler).chat(MESSAGES)
    assert info.value.__cause__ is exc  # 원인 보존


@pytest.mark.parametrize("status", [400, 404, 500, 503])
async def test_http_error_status_becomes_response_error(status):
    c = make_client(lambda req: httpx.Response(status, text="Loading model"))
    with pytest.raises(LLMResponseError) as info:
        await c.chat(MESSAGES)
    assert str(status) in str(info.value)
    assert not isinstance(info.value, LLMConnectionError)  # 연결 실패와 구분된다


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={}),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"choices": [{}]}),
        httpx.Response(200, json={"choices": [{"message": {}}]}),
        httpx.Response(200, json=[1, 2, 3]),
        # tool_calls 형식 오류
        httpx.Response(200, json=tool_call_body("", [{"type": "function", "function": {"name": "web_search", "arguments": "{}"}}])),
        httpx.Response(200, json=tool_call_body("", [{"id": "c1", "type": "function"}])),
        httpx.Response(200, json=tool_call_body("", [{"id": "c1", "function": {"arguments": "{}"}}])),
        httpx.Response(200, json=tool_call_body("", [raw_call("c1", "web_search", {"query": "x"})])),
        httpx.Response(200, json=tool_call_body("", "not-a-list")),
        httpx.Response(200, json=tool_call_body("", ["x"])),
    ],
    ids=[
        "not-json", "empty-object", "empty-choices", "no-message", "no-content", "json-array",
        "tool-call-no-id", "tool-call-no-function", "tool-call-no-name", "arguments-not-string",
        "tool-calls-not-list", "tool-call-not-object",
    ],
)
async def test_malformed_body_becomes_response_error(response):
    with pytest.raises(LLMResponseError):
        await make_client(lambda req: response).chat(MESSAGES)


def test_exceptions_share_llm_error_parent():
    assert issubclass(LLMConnectionError, LLMError)
    assert issubclass(LLMResponseError, LLMError)
    assert not issubclass(LLMConnectionError, LLMResponseError)


async def test_real_closed_port_raises_connection_error():
    """mock 이 아닌 진짜 네트워크: 아무도 듣지 않는 포트에 연결하면 LLMConnectionError.
    (= 'llama-server 를 끈 상태에서 전용 예외가 나는지' 확인)"""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    # with 를 벗어나 소켓이 닫혔으므로 이 포트는 비어 있다.
    async with httpx.AsyncClient() as http:
        c = LLMClient(http, LLMSettings(_env_file=None, base_url=f"http://127.0.0.1:{port}", timeout=5))
        with pytest.raises(LLMConnectionError):
            await c.chat(MESSAGES)


# ---------- Depends 용 제공자 ----------

async def test_get_llm_client_is_shared_and_close_resets():
    await client_module.close_llm_client()
    first = client_module.get_llm_client()
    assert client_module.get_llm_client() is first  # 프로세스 안에서 하나를 공유
    await client_module.close_llm_client()
    assert client_module.get_llm_client() is not first  # 닫으면 다음 호출 때 새로 만든다
    await client_module.close_llm_client()
