"""llm 모듈의 FastAPI Depends 용 제공자.

프로세스 전체에서 AsyncClient 하나를 공유한다. 첫 호출 때 만들고, 서버 종료 시 close_llm_client() 로 닫는다.
client.py 는 통신만 하고, 객체를 만들어 공유하고 닫는 일은 여기서 한다.
"""
import httpx

from src.llm.client import LLMClient
from src.llm.config import LLMSettings

_client: LLMClient | None = None
_http: httpx.AsyncClient | None = None


def get_llm_client() -> LLMClient:
    global _client, _http
    if _client is None:
        _http = httpx.AsyncClient()
        _client = LLMClient(_http, LLMSettings())
    return _client


async def close_llm_client() -> None:
    global _client, _http
    if _http is not None:
        await _http.aclose()
    _client = _http = None
