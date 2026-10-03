"""llm/client.py 단위 테스트 (인프라 레이어).

httpx.MockTransport 로 llama-server 를 흉내 낸다. 실제 서버는 필요 없다.
검증 대상: 요청 변환(내부 형식 → 서버 JSON), 응답 변환, 모든 실패 경로의 내부 예외 변환.
"""
import json
import socket

import httpx
import pytest

from src.llm import client as client_module
from src.llm.client import LLMClient, Message
from src.llm.config import LLMSettings
from src.llm.exceptions import LLMConnectionError, LLMError, LLMResponseError

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
    assert await c.chat(MESSAGES) == "저는 비서입니다."


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
    assert await c.chat(MESSAGES) == raw


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
    ],
    ids=["not-json", "empty-object", "empty-choices", "no-message", "no-content", "json-array"],
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
