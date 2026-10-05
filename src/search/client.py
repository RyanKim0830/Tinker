"""SearXNG 클라이언트 (인프라 레이어).

역할: SearXNG 의 JSON API(GET /search?format=json)와 통신한다.
- 서버 JSON → 검색 결과 목록(SearchResult) 변환
- 외부 에러를 search/exceptions.py 의 내부 예외로 변환
- 응답이 없었던 엔진 목록을 로그로 남긴다
결과를 몇 개 쓸지, 어떤 문자열로 만들지는 모른다. (service.py 의 일)
"""
import logging
from dataclasses import dataclass

import httpx

from src.search.config import SearchSettings
from src.search.exceptions import SearchConnectionError, SearchResponseError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """검색 결과 한 건. 서버 JSON 형식은 모른다."""

    title: str
    url: str
    content: str  # 스니펫. SearXNG 가 안 주는 결과는 빈 문자열


class SearchClient:
    def __init__(self, http: httpx.AsyncClient, settings: SearchSettings):
        # AsyncClient 는 밖에서 만들어 받는다 (연결 재사용, 테스트에서 가짜 transport 로 교체).
        self._http = http
        self._settings = settings

    async def search(self, query: str) -> list[SearchResult]:
        """검색어로 SearXNG 를 한 번 호출하고 결과 전체를 서버가 준 순서대로 돌려준다. 결과가 0개면 빈 목록."""
        s = self._settings
        try:
            resp = await self._http.get(
                f"{s.searxng_url}/search", params={"q": query, "format": "json"}, timeout=s.timeout
            )
        except httpx.TransportError as e:  # 연결 실패·타임아웃·전송 중 끊김
            raise SearchConnectionError(f"SearXNG 에 연결하지 못했다 ({s.searxng_url}): {e!r}") from e

        if resp.status_code != 200:
            raise SearchResponseError(f"SearXNG 가 HTTP {resp.status_code} 를 돌려줬다: {resp.text[:200]}")

        # 서버 응답 JSON → 결과 목록. title·url 이 없는 결과가 있으면 형식이 다른 것으로 본다.
        try:
            body = resp.json()
            results = [
                SearchResult(title=r["title"], url=r["url"], content=r.get("content") or "")
                for r in body["results"]
            ]
            unresponsive = body.get("unresponsive_engines", [])
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise SearchResponseError(f"응답 형식이 예상과 다르다: {resp.text[:200]}") from e

        # 일부 엔진이 응답하지 않아도 결과가 있으면 정상으로 본다. 어떤 엔진이 빠졌는지만 남긴다.
        logger.info("SearXNG 응답 없는 엔진: %s", unresponsive)
        return results
