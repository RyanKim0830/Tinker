"""앱 전체 흐름 테스트 (router → service → client).

LLM 서버(llama-server)만 httpx.MockTransport 로 바꾸고 나머지 세 레이어는 진짜를 쓴다.
레이어 사이의 연결(Depends 주입, 예외 변환 사슬)이 실제로 이어지는지 확인한다.
"""
import json

import httpx
import pytest

from src.chat.service import SYSTEM_PROMPT
from src.llm.client import LLMClient, get_llm_client
from src.llm.config import LLMSettings
from src.main import app


class FakeLlamaServer:
    """OpenAI 호환 응답을 흉내 내는 llama-server. 받은 요청 본문을 기록한다."""

    def __init__(self):
        self.requests: list[dict] = []
        self.fail: httpx.Response | Exception | None = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if isinstance(self.fail, Exception):
            raise self.fail
        if self.fail is not None:
            return self.fail
        body = json.loads(req.content)
        self.requests.append(body)
        n = len(self.requests)
        return httpx.Response(200, json={"choices": [{"message": {"content": f"답{n}"}}]})


@pytest.fixture
def llama():
    server = FakeLlamaServer()
    llm = LLMClient(httpx.AsyncClient(transport=httpx.MockTransport(server)), LLMSettings(_env_file=None))
    app.dependency_overrides[get_llm_client] = lambda: llm
    yield server
    app.dependency_overrides.clear()


@pytest.fixture
async def http():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_two_requests_share_history_through_all_layers(http, llama):
    r1 = await http.post("/chat", json={"query": "내 이름은 철수야"})
    r2 = await http.post("/chat", json={"query": "내 이름이 뭐지?"})
    assert (r1.json(), r2.json()) == ({"reply": "답1"}, {"reply": "답2"})

    assert llama.requests[0]["messages"] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "내 이름은 철수야"},
    ]
    assert llama.requests[1]["messages"] == [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "내 이름은 철수야"},
        {"role": "assistant", "content": "답1"},
        {"role": "user", "content": "내 이름이 뭐지?"},
    ]


async def test_llama_server_down_is_503_and_history_stays_clean(http, llama):
    llama.fail = httpx.ConnectError("refused")
    assert (await http.post("/chat", json={"query": "q1"})).status_code == 503

    llama.fail = None  # 서버가 살아남
    assert (await http.post("/chat", json={"query": "q2"})).json() == {"reply": "답1"}
    assert [m["content"] for m in llama.requests[0]["messages"]] == [SYSTEM_PROMPT, "q2"]  # q1 은 이력에 없다


@pytest.mark.parametrize("fail", [httpx.Response(500, text="boom"), httpx.Response(200, text="not json")], ids=["http-500", "bad-json"])
async def test_llama_server_bad_response_is_502(http, llama, fail):
    llama.fail = fail
    assert (await http.post("/chat", json={"query": "q"})).status_code == 502


async def test_invalid_request_never_reaches_llama(http, llama):
    assert (await http.post("/chat", json={"query": 1})).status_code == 422
    assert llama.requests == []
