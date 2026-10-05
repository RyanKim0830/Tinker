"""cli.py 테스트.

서버(POST /chat)는 httpx.MockTransport 로 흉내 낸다. 입력은 미리 정한 줄 목록으로 주입하고 출력은 리스트에 모은다.
"""
import json

import httpx

import cli

BASE = "http://test"


def make_http(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def scripted(*lines: str):
    """입력 줄을 순서대로 돌려주고, 다 쓰면 EOF(Ctrl+D)를 낸다."""
    it = iter(lines)

    async def read_line() -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError

    return read_line


async def run(handler, *lines: str) -> list[str]:
    out: list[str] = []
    async with make_http(handler) as http:
        await cli.chat_loop(http, BASE, scripted(*lines), out.append)
    return out[1:]  # 첫 줄은 안내 문구


async def test_ask_posts_query_and_returns_reply():
    seen = {}

    def handler(req):
        seen.update(method=req.method, url=str(req.url), body=json.loads(req.content))
        return httpx.Response(200, json={"reply": "안녕하세요."})

    async with make_http(handler) as http:
        assert await cli.ask(http, BASE, "안녕") == "안녕하세요."
    assert seen == {"method": "POST", "url": "http://test/chat", "body": {"query": "안녕"}}


async def test_conversation_continues_over_multiple_turns():
    queries = []

    def handler(req):
        queries.append(json.loads(req.content)["query"])
        return httpx.Response(200, json={"reply": f"답{len(queries)}"})

    out = await run(handler, "첫 질문", "두 번째 질문")
    assert queries == ["첫 질문", "두 번째 질문"]
    assert out == ["답1", "답2"]


async def test_exit_command_stops_before_next_line():
    queries = []

    def handler(req):
        queries.append(1)
        return httpx.Response(200, json={"reply": "x"})

    await run(handler, "/exit", "이건 전송되면 안 된다")
    assert queries == []


async def test_eof_ends_loop_cleanly():
    out = await run(lambda req: httpx.Response(200, json={"reply": "x"}))  # 입력 없음 = 바로 EOF
    assert out == []


async def test_blank_lines_are_not_sent():
    queries = []

    def handler(req):
        queries.append(json.loads(req.content)["query"])
        return httpx.Response(200, json={"reply": "x"})

    await run(handler, "", "   ", "진짜 질문")
    assert queries == ["진짜 질문"]


async def test_connection_error_prints_hint_and_loop_continues():
    calls = []

    def handler(req):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json={"reply": "살아났다"})

    out = await run(handler, "q1", "q2")
    assert "서버에 연결할 수 없다" in out[0] and "python -m src.main" in out[0]
    assert out[1] == "살아났다"  # 한 번 실패해도 종료하지 않는다


async def test_http_error_prints_status_and_detail_and_continues():
    def handler(req):
        return httpx.Response(503, json={"detail": "LLM 서버에 연결할 수 없다"})

    out = await run(handler, "q1", "q2")
    assert len(out) == 2
    assert all("503" in line and "LLM 서버에 연결할 수 없다" in line for line in out)


async def test_real_closed_port_prints_connection_hint():
    """mock 이 아닌 진짜 네트워크: 서버가 안 떠 있는 포트에 연결."""
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    out: list[str] = []
    async with httpx.AsyncClient() as http:
        await cli.chat_loop(http, f"http://127.0.0.1:{port}", scripted("안녕"), out.append)
    assert "서버에 연결할 수 없다" in out[1]


async def test_request_timeout_is_450_seconds():
    """서버가 LLM 을 최대 2번 + 검색을 하므로 CLI 는 450초까지 기다린다."""
    seen = {}

    def handler(req: httpx.Request) -> httpx.Response:
        seen["timeout"] = req.extensions["timeout"]
        return httpx.Response(200, json={"reply": "ok"})

    async with make_http(handler) as http:
        await cli.ask(http, BASE, "q")
    assert cli.TIMEOUT == 450.0
    assert seen["timeout"]["read"] == 450.0
