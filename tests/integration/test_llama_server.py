"""실제 llama-server 를 대상으로 하는 통합 테스트.

실행:  scripts/llama-server.sh 를 먼저 띄운 뒤  pytest -m integration
기본 실행(pytest)에서는 제외된다 (pytest.ini 의 addopts).

서버가 없으면 skip 이 아니라 '실패'시킨다: 안 돌았는데 통과한 것처럼 보이는 걸 막기 위해서다.
LLM 답변은 매번 조금씩 달라지므로 정확한 문장이 아니라 '성질'(thinking 없음, 한글, 기억)만 검사한다.
"""
import json
import re

import httpx
import pytest

from src.chat import service
from src.chat.service import ChatService
from src.llm.client import LLMClient
from src.llm.config import LLMSettings
from src.main import app
from src.message import Message

pytestmark = pytest.mark.integration

SETTINGS = LLMSettings(_env_file=None)  # 기본값(http://localhost:8080)을 쓴다. .env 로 바꿨다면 LLM_BASE_URL 환경변수로.
HANGUL = re.compile(r"[가-힣]")


@pytest.fixture
async def llm():
    async with httpx.AsyncClient() as http:
        try:
            health = await http.get(f"{SETTINGS.base_url}/health", timeout=5)
        except httpx.TransportError:
            pytest.fail(f"llama-server 가 {SETTINGS.base_url} 에 없다. scripts/llama-server.sh 를 먼저 실행할 것")
        if health.status_code != 200:
            pytest.fail(f"llama-server 가 준비되지 않았다 (/health → {health.status_code}). 모델 로딩이 끝날 때까지 기다릴 것")
        yield LLMClient(http, SETTINGS)


async def test_client_gets_non_empty_reply(llm):
    reply = await llm.chat([Message("system", "짧게 답한다."), Message("user", "안녕")])
    assert reply.role == "assistant" and reply.content.strip() and reply.tool_calls == ()


async def test_reply_has_no_thinking_content(llm):
    """--reasoning off 가 먹었는지: 원본 응답에 reasoning_content 가 비어 있고 본문에 think 태그가 없어야 한다."""
    async with httpx.AsyncClient() as http:
        r = await http.post(
            f"{SETTINGS.base_url}/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "1+1은?"}], "stream": False},
            timeout=SETTINGS.timeout,
        )
    msg = r.json()["choices"][0]["message"]
    assert not msg.get("reasoning_content"), f"thinking 이 켜져 있다: {msg.get('reasoning_content')!r}"
    assert "<think>" not in msg["content"] and "</think>" not in msg["content"]


async def test_replies_in_korean_with_system_prompt(llm):
    svc = ChatService(llm, [])
    reply = await svc.chat("Hello, who are you?")  # 영어로 물어도 시스템 프롬프트대로 한국어로 답해야 한다
    assert HANGUL.search(reply), f"한글 답변이 아니다: {reply!r}"


async def test_second_answer_remembers_first_turn(llm):
    """2단계 확인: 두 번째 답이 첫 번째 대화 내용을 기억하는가 (실제 모델)."""
    svc = ChatService(llm, [])
    await svc.chat("내 이름은 철수야. 기억해줘.")
    reply = await svc.chat("내 이름이 뭐라고 했지?")
    assert "철수" in reply, f"기억하지 못했다: {reply!r}"


async def test_full_app_conversation_over_http(llm):
    """3단계 확인(자동화): 앱의 /chat 을 실제 llama-server 와 연결해 두 번 호출."""
    from src.llm.client import get_llm_client

    app.dependency_overrides[get_llm_client] = lambda: llm
    service._history.clear()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            r1 = await c.post("/chat", json={"query": "내 이름은 영희야."})
            r2 = await c.post("/chat", json={"query": "내 이름이 뭐지?"})
            bad = await c.post("/chat", json={"query": 123})
    finally:
        app.dependency_overrides.clear()
        service._history.clear()
    assert r1.status_code == 200 and r2.status_code == 200
    assert "영희" in r2.json()["reply"]
    assert bad.status_code == 422


# ---------- 툴 콜링 ----------

WEB_SEARCH = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "웹을 검색한다. 최신 정보나 모르는 사실이 필요할 때 쓴다.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "검색어"}}, "required": ["query"]},
    },
}


async def test_tools_request_returns_parsed_tool_calls(llm):
    """tools 를 보내면 서버의 tool_calls 가 Message.tool_calls 로 파싱된다. (모델이 부르기로 하는 질문을 쓴다)"""
    reply = await llm.chat(
        [Message("system", "최신 정보가 필요하면 web_search 툴을 쓴다."), Message("user", "오늘 서울 날씨 검색해서 알려줘")],
        [WEB_SEARCH],
    )
    assert len(reply.tool_calls) >= 1
    call = reply.tool_calls[0]
    assert call.id and call.name == "web_search"
    assert json.loads(call.arguments)["query"].strip()


async def test_tool_result_round_trip_gives_final_answer(llm):
    """assistant(tool_calls) + tool 결과를 짝으로 다시 보내면 서버가 받아들이고 본문으로 답한다."""
    first = await llm.chat(
        [Message("system", "최신 정보가 필요하면 web_search 툴을 쓴다."), Message("user", "오늘 서울 날씨 검색해서 알려줘")],
        [WEB_SEARCH],
    )
    assert first.tool_calls
    history = [
        Message("system", "검색 결과가 있으면 그것을 근거로 답한다. 한국어로 짧게."),
        Message("user", "오늘 서울 날씨 검색해서 알려줘"),
        first,
        *[Message("tool", "[1] 서울 날씨 (http://w)\n서울 맑음, 기온 19도", tool_call_id=tc.id) for tc in first.tool_calls],
    ]
    final = await llm.chat(history)  # 상한 도달 때처럼 tools 없이
    assert final.content.strip() and final.tool_calls == ()
