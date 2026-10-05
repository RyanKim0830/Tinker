"""웹 검색 서비스 (비즈니스 레이어).

역할: 검색어로 SearXNG 를 호출하고, 상위 N개 결과를 LLM 에 넘길 문자열로 만든다.
형식: "[번호] 제목 (URL)\n내용" 을 빈 줄로 이어 붙인다.
HTTP·SearXNG 통신 방식은 모른다. 실패는 SearchError 계열 예외로 올리고, 문자열로 바꾸는 건 호출하는 쪽의 일이다.
"""
import logging

from src.search.client import SearchClient, SearchResult

logger = logging.getLogger(__name__)

# 결과가 하나도 없을 때 LLM 에 돌려주는 문장. 예외가 아니다.
NO_RESULTS = "검색 결과가 없다."


def format_results(results: list[SearchResult]) -> str:
    """검색 결과를 번호를 붙여 문자열로 만든다. 번호는 1부터."""
    return "\n\n".join(f"[{i}] {r.title} ({r.url})\n{r.content}" for i, r in enumerate(results, start=1))


class SearchService:
    def __init__(self, client: SearchClient, result_count: int):
        self._client = client
        self._result_count = result_count

    async def search(self, query: str) -> str:
        """검색어로 검색해 상위 result_count 개를 포맷한 문자열로 돌려준다. 결과가 없으면 NO_RESULTS."""
        results = await self._client.search(query)
        used = results[: self._result_count]
        logger.info("검색 query=%r 결과 %d개 (LLM 에 %d개)", query, len(results), len(used))
        if not used:
            return NO_RESULTS
        return format_results(used)
