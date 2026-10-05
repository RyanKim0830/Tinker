"""search/client.py 단위 테스트 (인프라 레이어).

httpx.MockTransport 로 SearXNG 를 흉내 낸다. 실제 서버는 필요 없다.
검증 대상: 요청 형식, 응답 변환, 응답 없는 엔진 로깅, 모든 실패 경로의 내부 예외 변환.
"""
import logging
import socket

import httpx
import pytest

from src.search.client import SearchClient, SearchResult
from src.search.config import SearchSettings
from src.search.exceptions import SearchConnectionError, SearchError, SearchResponseError


def body(results: list[dict], unresponsive: list | None = None) -> dict:
    """SearXNG format=json 응답 형태 (쓰는 필드만)."""
    return {"query": "q", "results": results, "unresponsive_engines": unresponsive or []}


def make_client(handler, **settings) -> SearchClient:
    """handler(request) -> httpx.Response 를 서버로 쓰는 클라이언트. .env 영향을 받지 않게 env_file 을 끈다."""
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return SearchClient(http, SearchSettings(_env_file=None, **settings))


# ---------- 정상 경로 ----------

async def test_request_goes_to_search_endpoint_with_json_format():
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["method"], seen["path"], seen["params"] = req.method, req.url.path, dict(req.url.params)
        seen["host"] = req.url.host
        return httpx.Response(200, json=body([]))

    await make_client(handler, searxng_url="http://example:9999").search("서울 날씨")
    assert seen == {"method": "GET", "path": "/search", "params": {"q": "서울 날씨", "format": "json"}, "host": "example"}


async def test_results_are_converted_in_server_order():
    raw = [
        {"title": "A", "url": "http://a", "content": "가"},
        {"title": "B", "url": "http://b", "content": "나", "engine": "x", "score": 1.0},  # 쓰지 않는 필드는 무시
    ]
    c = make_client(lambda req: httpx.Response(200, json=body(raw)))
    assert await c.search("q") == [SearchResult("A", "http://a", "가"), SearchResult("B", "http://b", "나")]


async def test_client_returns_all_results_without_limit():
    """몇 개를 쓸지는 서비스의 일이다. 클라이언트는 자르지 않는다."""
    raw = [{"title": f"t{i}", "url": f"http://{i}", "content": ""} for i in range(20)]
    c = make_client(lambda req: httpx.Response(200, json=body(raw)))
    assert len(await c.search("q")) == 20


async def test_empty_results_is_not_an_error():
    c = make_client(lambda req: httpx.Response(200, json=body([])))
    assert await c.search("q") == []


@pytest.mark.parametrize("raw", [{}, {"content": None}], ids=["no-content", "null-content"])
async def test_missing_content_becomes_empty_string(raw):
    c = make_client(lambda req: httpx.Response(200, json=body([{"title": "T", "url": "http://t", **raw}])))
    assert await c.search("q") == [SearchResult("T", "http://t", "")]


async def test_unresponsive_engines_are_logged(caplog):
    unresponsive = [["brave", "too many requests"], ["duckduckgo", "CAPTCHA"]]
    c = make_client(lambda req: httpx.Response(200, json=body([], unresponsive)))
    with caplog.at_level(logging.INFO, logger="src.search.client"):
        await c.search("q")
    assert "brave" in caplog.text and "duckduckgo" in caplog.text


async def test_response_without_unresponsive_field_is_ok():
    c = make_client(lambda req: httpx.Response(200, json={"results": []}))
    assert await c.search("q") == []


# ---------- 실패 경로: 전부 search 전용 예외로 바뀌어야 한다 ----------

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

    with pytest.raises(SearchConnectionError) as info:
        await make_client(handler).search("q")
    assert info.value.__cause__ is exc  # 원인 보존


@pytest.mark.parametrize("status", [400, 403, 429, 500, 503])
async def test_http_error_status_becomes_response_error(status):
    """403 은 settings.yml 에서 json 형식을 허용하지 않았을 때 SearXNG 가 주는 상태다."""
    c = make_client(lambda req: httpx.Response(status, text="Forbidden"))
    with pytest.raises(SearchResponseError) as info:
        await c.search("q")
    assert str(status) in str(info.value)
    assert not isinstance(info.value, SearchConnectionError)  # 연결 실패와 구분된다


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>not json</html>"),
        httpx.Response(200, json={}),
        httpx.Response(200, json=[1, 2, 3]),
        httpx.Response(200, json={"results": None}),
        httpx.Response(200, json={"results": [{"url": "http://a"}]}),
        httpx.Response(200, json={"results": [{"title": "A"}]}),
        httpx.Response(200, json={"results": ["x"]}),
    ],
    ids=["not-json", "empty-object", "json-array", "results-null", "no-title", "no-url", "result-not-object"],
)
async def test_malformed_body_becomes_response_error(response):
    with pytest.raises(SearchResponseError):
        await make_client(lambda req: response).search("q")


def test_exceptions_share_search_error_parent():
    assert issubclass(SearchConnectionError, SearchError)
    assert issubclass(SearchResponseError, SearchError)
    assert not issubclass(SearchConnectionError, SearchResponseError)


async def test_real_closed_port_raises_connection_error():
    """mock 이 아닌 진짜 네트워크: 아무도 듣지 않는 포트에 연결하면 SearchConnectionError."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    async with httpx.AsyncClient() as http:
        c = SearchClient(http, SearchSettings(_env_file=None, searxng_url=f"http://127.0.0.1:{port}", timeout=5))
        with pytest.raises(SearchConnectionError):
            await c.search("q")


# ---------- 설정 ----------

def test_default_settings():
    s = SearchSettings(_env_file=None)
    assert (s.searxng_url, s.timeout, s.result_count) == ("http://localhost:8888", 15.0, 5)


def test_settings_read_search_prefixed_env(monkeypatch):
    monkeypatch.setenv("SEARCH_SEARXNG_URL", "http://other:1")
    monkeypatch.setenv("SEARCH_TIMEOUT", "3")
    monkeypatch.setenv("SEARCH_RESULT_COUNT", "2")
    s = SearchSettings(_env_file=None)
    assert (s.searxng_url, s.timeout, s.result_count) == ("http://other:1", 3.0, 2)
