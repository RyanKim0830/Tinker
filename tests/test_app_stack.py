"""앱 전체 흐름 테스트 (router → service → client).

LLM 서버(llama-server)와 검색 서버(SearXNG)만 httpx.MockTransport 로 바꾸고 나머지 레이어는 진짜를 쓴다.
레이어 사이의 연결(Depends 주입, 예외 변환 사슬, 툴 콜링 루프)이 실제로 이어지는지 확인한다.
"""
import json

import httpx
import pytest

from src.chat import tools
from src.chat.service import build_system_prompt
from src.llm.client import LLMClient, get_llm_client
from src.llm.config import LLMSettings
from src.main import app
from src.search.client import SearchClient, get_search_client
from src.search.config import SearchSettings
from src.search.service import NO_RESULTS


def llama_tool_call(query: str, id_: str = "c1") -> dict:
    """llama-server 가 툴 호출을 줄 때의 응답 (content 는 비어 있다)."""
    call = {"type": "function", "id": id_, "function": {"name": "web_search", "arguments": json.dumps({"query": query}, ensure_ascii=False)}}
    return {"choices": [{"finish_reason": "tool_calls", "message": {"role": "assistant", "content": "", "tool_calls": [call]}}]}


class FakeLlamaServer:
    """OpenAI 호환 응답을 흉내 내는 llama-server. 받은 요청 본문을 기록한다.

    script 가 있으면 요청 순서대로 그 항목을 쓰고(dict 는 응답 본문, 예외는 던진다), 없으면 "답N" 을 돌려준다.
    """

    def __init__(self):
        self.requests: list[dict] = []
        self.script: list[dict | Exception] = []
        self.fail: httpx.Response | Exception | None = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if isinstance(self.fail, Exception):
            raise self.fail
        if self.fail is not None:
            return self.fail
        self.requests.append(json.loads(req.content))
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return httpx.Response(200, json=item)
        return httpx.Response(200, json={"choices": [{"message": {"content": f"답{len(self.requests)}"}}]})


class FakeSearxng:
    """SearXNG JSON API 를 흉내 낸다. 받은 쿼리 파라미터를 기록한다."""

    def __init__(self):
        self.requests: list[dict] = []
        self.results = [{"title": f"제목{i}", "url": f"http://site/{i}", "content": f"내용{i}"} for i in range(1, 9)]
        self.fail: httpx.Response | Exception | None = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if isinstance(self.fail, Exception):
            raise self.fail
        if self.fail is not None:
            return self.fail
        self.requests.append(dict(req.url.params))
        return httpx.Response(200, json={"results": self.results, "unresponsive_engines": []})


@pytest.fixture
def llama():
    server = FakeLlamaServer()
    llm = LLMClient(httpx.AsyncClient(transport=httpx.MockTransport(server)), LLMSettings(_env_file=None))
    app.dependency_overrides[get_llm_client] = lambda: llm
    yield server
    app.dependency_overrides.clear()


@pytest.fixture
def searxng():
    server = FakeSearxng()
    client = SearchClient(httpx.AsyncClient(transport=httpx.MockTransport(server)), SearchSettings(_env_file=None))
    app.dependency_overrides[get_search_client] = lambda: client
    yield server
    app.dependency_overrides.pop(get_search_client, None)


@pytest.fixture
async def http():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def system_content(request_body: dict) -> str:
    assert request_body["messages"][0]["role"] == "system"
    return request_body["messages"][0]["content"]


# ---------- 툴 없이 끝나는 대화 ----------

async def test_two_requests_share_history_through_all_layers(http, llama, searxng):
    r1 = await http.post("/chat", json={"query": "내 이름은 철수야"})
    r2 = await http.post("/chat", json={"query": "내 이름이 뭐지?"})
    assert (r1.json(), r2.json()) == ({"reply": "답1"}, {"reply": "답2"})

    assert llama.requests[0]["messages"][1:] == [{"role": "user", "content": "내 이름은 철수야"}]
    assert llama.requests[1]["messages"][1:] == [
        {"role": "user", "content": "내 이름은 철수야"},
        {"role": "assistant", "content": "답1"},
        {"role": "user", "content": "내 이름이 뭐지?"},
    ]
    assert searxng.requests == []  # 잡담은 검색하지 않는다


async def test_system_prompt_has_base_text_date_and_search_rule(http, llama, searxng):
    await http.post("/chat", json={"query": "안녕"})
    prompt = system_content(llama.requests[0])
    assert prompt.startswith("너는 사용자의 개인 비서다. 한국어로 짧게 답한다.")
    assert "오늘 날짜는" in prompt and prompt.endswith("검색 결과가 있으면 그것을 근거로 답한다.")


async def test_first_request_offers_web_search_tool(http, llama, searxng):
    await http.post("/chat", json={"query": "안녕"})
    assert llama.requests[0]["tools"] == tools.TOOLS


# ---------- 검색이 필요한 대화 ----------

async def test_search_flow_through_all_layers(http, llama, searxng):
    llama.script = [llama_tool_call("서울 날씨"), {"choices": [{"message": {"content": "서울은 맑아요."}}]}]
    r = await http.post("/chat", json={"query": "오늘 서울 날씨?"})

    assert r.status_code == 200 and r.json() == {"reply": "서울은 맑아요."}
    assert searxng.requests == [{"q": "서울 날씨", "format": "json"}]

    first, second = llama.requests
    assert "tools" in first and "tools" not in second  # 상한(2)에 도달한 마지막 왕복은 tools 없이
    msgs = second["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "tool"]
    assert msgs[2]["tool_calls"][0]["id"] == "c1" and msgs[3]["tool_call_id"] == "c1"  # 짝
    # 스니펫은 상위 5개(설정값), 포맷은 "[번호] 제목 (URL)\n내용"
    assert msgs[3]["content"].startswith("[1] 제목1 (http://site/1)\n내용1")
    assert "[5] 제목5" in msgs[3]["content"] and "[6]" not in msgs[3]["content"]


async def test_follow_up_request_carries_search_result(http, llama, searxng):
    llama.script = [llama_tool_call("서울 날씨"), {"choices": [{"message": {"content": "맑아요."}}]}]
    await http.post("/chat", json={"query": "서울 날씨?"})
    await http.post("/chat", json={"query": "방금 검색한 첫 번째 출처가 뭐였지?"})

    follow_up = llama.requests[2]["messages"]
    assert [m["role"] for m in follow_up] == ["system", "user", "assistant", "tool", "assistant", "user"]
    assert "http://site/1" in follow_up[3]["content"]  # 검색 원문이 이력에 남아 있다


async def test_search_server_down_does_not_break_chat(http, llama, searxng):
    """검색 쪽 실패는 서비스를 죽이지 않는다: 실패 문자열이 tool 결과로 LLM 에 가고 답은 정상으로 온다."""
    searxng.fail = httpx.ConnectError("refused")
    llama.script = [llama_tool_call("서울 날씨"), {"choices": [{"message": {"content": "검색이 안 돼요."}}]}]
    r = await http.post("/chat", json={"query": "서울 날씨?"})

    assert r.status_code == 200 and r.json() == {"reply": "검색이 안 돼요."}
    assert llama.requests[1]["messages"][-1]["content"].startswith("검색 실패")


@pytest.mark.parametrize("fail", [httpx.Response(403, text="Forbidden"), httpx.Response(200, text="<html>")], ids=["http-403", "not-json"])
async def test_search_bad_response_does_not_break_chat(http, llama, searxng, fail):
    searxng.fail = fail
    llama.script = [llama_tool_call("q"), {"choices": [{"message": {"content": "못 찾았어요."}}]}]
    r = await http.post("/chat", json={"query": "q"})
    assert r.status_code == 200
    assert llama.requests[1]["messages"][-1]["content"].startswith("검색 실패")


async def test_search_with_zero_results_does_not_break_chat(http, llama, searxng):
    searxng.results = []
    llama.script = [llama_tool_call("없는 것"), {"choices": [{"message": {"content": "없어요."}}]}]
    assert (await http.post("/chat", json={"query": "q"})).status_code == 200
    assert llama.requests[1]["messages"][-1]["content"] == NO_RESULTS


# ---------- LLM 실패 ----------

async def test_llama_server_down_is_503_and_history_stays_clean(http, llama, searxng):
    llama.fail = httpx.ConnectError("refused")
    assert (await http.post("/chat", json={"query": "q1"})).status_code == 503

    llama.fail = None  # 서버가 살아남
    assert (await http.post("/chat", json={"query": "q2"})).json() == {"reply": "답1"}
    assert [m["content"] for m in llama.requests[0]["messages"][1:]] == ["q2"]  # q1 은 이력에 없다


async def test_llama_failure_after_search_is_503_and_nothing_is_saved(http, llama, searxng):
    llama.script = [llama_tool_call("서울 날씨"), httpx.ReadTimeout("slow")]  # 검색까지 하고, 두 번째 왕복에서 LLM 이 끊긴다
    assert (await http.post("/chat", json={"query": "서울 날씨?"})).status_code == 503
    assert len(searxng.requests) == 1

    await http.post("/chat", json={"query": "다음"})
    assert [m["role"] for m in llama.requests[-1]["messages"]] == ["system", "user"]  # 실패한 턴(검색 포함)은 이력에 없다


@pytest.mark.parametrize("fail", [httpx.Response(500, text="boom"), httpx.Response(200, text="not json")], ids=["http-500", "bad-json"])
async def test_llama_server_bad_response_is_502(http, llama, searxng, fail):
    llama.fail = fail
    assert (await http.post("/chat", json={"query": "q"})).status_code == 502


async def test_invalid_request_never_reaches_llama(http, llama, searxng):
    assert (await http.post("/chat", json={"query": 1})).status_code == 422
    assert llama.requests == []
