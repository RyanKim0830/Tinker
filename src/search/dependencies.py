"""search 모듈의 FastAPI Depends 용 제공자.

클라이언트는 프로세스 전체에서 AsyncClient 하나를 공유한다. 첫 호출 때 만들고, 서버 종료 시 close_search_client() 로 닫는다.
서비스는 요청마다 새로 만든다 (공유하는 상태가 없다).
client.py·service.py 는 기능만 하고, 객체를 만들어 공유하고 닫는 일은 여기서 한다.
"""
import httpx
from fastapi import Depends

from src.search.client import SearchClient
from src.search.config import SearchSettings
from src.search.service import SearchService

_client: SearchClient | None = None
_http: httpx.AsyncClient | None = None


def get_search_client() -> SearchClient:
    global _client, _http
    if _client is None:
        _http = httpx.AsyncClient()
        _client = SearchClient(_http, SearchSettings())
    return _client


async def close_search_client() -> None:
    global _client, _http
    if _http is not None:
        await _http.aclose()
    _client = _http = None


def get_search_service(client: SearchClient = Depends(get_search_client)) -> SearchService:
    """클라이언트는 주입받고, 결과 개수는 설정에서 읽는다."""
    return SearchService(client, SearchSettings().result_count)
