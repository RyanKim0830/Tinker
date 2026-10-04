"""chat/router.py + schemas.py 테스트 (프레젠테이션 레이어).

요청 검증(422), 정상 응답 형식, 서비스 예외 → HTTP 상태 코드 변환을 본다.
서비스는 가짜로 바꾼다 (dependency_overrides). 서버를 띄우지 않고 ASGI 로 앱을 직접 호출한다.
"""
import logging

import httpx
import pytest

from src.chat.router import router  # noqa: F401  (임포트만으로 라우트 등록 확인)
from src.chat.service import ChatFailedError, ChatUnavailableError, get_chat_service
from src.main import app


class FakeService:
    def __init__(self, reply: str = "답", error: Exception | None = None):
        self.reply, self.error, self.queries = reply, error, []

    async def chat(self, query: str) -> str:
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture
def use_service():
    """앱의 서비스 의존성을 가짜로 바꾸고, 끝나면 되돌린다."""

    def _use(fake: FakeService) -> FakeService:
        app.dependency_overrides[get_chat_service] = lambda: fake
        return fake

    yield _use
    app.dependency_overrides.clear()


@pytest.fixture
async def http():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------- 정상 ----------

async def test_chat_returns_reply_in_confirmed_shape(http, use_service):
    use_service(FakeService("안녕하세요."))
    r = await http.post("/chat", json={"query": "안녕"})
    assert r.status_code == 200
    assert r.json() == {"reply": "안녕하세요."}  # 키는 reply 하나뿐


async def test_chat_passes_query_to_service_unchanged(http, use_service):
    fake = use_service(FakeService())
    await http.post("/chat", json={"query": "  공백과 한글 😀 포함  "})
    assert fake.queries == ["  공백과 한글 😀 포함  "]


async def test_whitespace_only_query_is_accepted(http, use_service):
    """공백만 있는 질문은 막지 않는다 (라우터는 판단하지 않는다). 바꾸려면 docs/open-items.md 참고."""
    fake = use_service(FakeService())
    r = await http.post("/chat", json={"query": "   "})
    assert r.status_code == 200 and fake.queries == ["   "]


# ---------- 잘못된 요청은 422, 서비스는 호출되지 않는다 ----------

@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": "안녕"},
        {"query": None},
        {"query": 123},
        {"query": ["a"]},
        {"query": ""},
    ],
    ids=["empty-object", "wrong-key", "null", "number", "list", "empty-string"],
)
async def test_invalid_json_body_is_422(http, use_service, body):
    fake = use_service(FakeService())
    r = await http.post("/chat", json=body)
    assert r.status_code == 422
    assert fake.queries == []


async def test_non_json_body_is_422(http, use_service):
    fake = use_service(FakeService())
    r = await http.post("/chat", content="그냥 텍스트", headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert fake.queries == []


async def test_no_body_is_422(http, use_service):
    use_service(FakeService())
    assert (await http.post("/chat")).status_code == 422


async def test_wrong_method_is_405(http, use_service):
    use_service(FakeService())
    assert (await http.get("/chat")).status_code == 405


# ---------- 서비스 예외 → HTTP 상태 ----------

async def test_unavailable_error_is_503(http, use_service):
    use_service(FakeService(error=ChatUnavailableError("down")))
    r = await http.post("/chat", json={"query": "안녕"})
    assert r.status_code == 503
    assert "detail" in r.json()


async def test_unavailable_error_logs_traceback(http, use_service, caplog):
    error = ChatUnavailableError("down")
    use_service(FakeService(error=error))
    with caplog.at_level(logging.ERROR, logger="src.chat.router"):
        response = await http.post("/chat", json={"query": "안녕"})
    assert response.status_code == 503
    records = [r for r in caplog.records if r.name == "src.chat.router"]
    assert len(records) == 1
    record = records[0]
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "chat 실패: LLM 서버 연결 불가"
    assert record.exc_info is not None
    assert record.exc_info[1] is error
    assert record.exc_info[2] is not None


async def test_failed_error_is_502(http, use_service):
    use_service(FakeService(error=ChatFailedError("bad")))
    r = await http.post("/chat", json={"query": "안녕"})
    assert r.status_code == 502


async def test_error_response_does_not_leak_internal_message(http, use_service):
    use_service(FakeService(error=ChatUnavailableError("http://localhost:8080 secret-internal")))
    r = await http.post("/chat", json={"query": "안녕"})
    assert "localhost" not in r.text and "secret-internal" not in r.text


async def test_unexpected_error_is_not_masked_as_503_or_502(use_service):
    """버그성 예외는 503/502 로 위장되지 않는다 (500 으로 드러난다)."""
    use_service(FakeService(error=RuntimeError("bug")))
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        assert (await c.post("/chat", json={"query": "안녕"})).status_code == 500


# ---------- 문서 ----------

async def test_docs_and_openapi_are_served(http):
    assert (await http.get("/docs")).status_code == 200
    spec = (await http.get("/openapi.json")).json()
    assert "/chat" in spec["paths"] and "post" in spec["paths"]["/chat"]
