"""search/service.py 단위 테스트 (비즈니스 레이어).

가짜 SearchClient 로 포맷과 개수 제한을 검증한다. HTTP 는 쓰지 않는다.
"""
import pytest

from src.search.client import SearchResult
from src.search.exceptions import SearchConnectionError
from src.search.service import NO_RESULTS, SearchService, format_results


class FakeClient:
    """SearchClient 대역. 정해 둔 결과를 돌려주거나 예외를 던진다."""

    def __init__(self, results=(), error: Exception | None = None):
        self.results = list(results)
        self.error = error
        self.queries: list[str] = []

    async def search(self, query: str) -> list[SearchResult]:
        self.queries.append(query)
        if self.error:
            raise self.error
        return self.results


def results(n: int) -> list[SearchResult]:
    return [SearchResult(f"제목{i}", f"http://site/{i}", f"내용{i}") for i in range(1, n + 1)]


def test_format_is_number_title_url_then_content():
    out = format_results([SearchResult("서울 날씨", "http://w", "맑음")])
    assert out == "[1] 서울 날씨 (http://w)\n맑음"


def test_format_separates_results_with_blank_line_and_numbers_from_one():
    out = format_results(results(2))
    assert out == "[1] 제목1 (http://site/1)\n내용1\n\n[2] 제목2 (http://site/2)\n내용2"


async def test_search_passes_query_through():
    client = FakeClient(results(1))
    await SearchService(client, 5).search("서울 날씨")
    assert client.queries == ["서울 날씨"]


async def test_search_uses_only_top_result_count():
    out = await SearchService(FakeClient(results(20)), 5).search("q")
    assert out.count("\n\n") == 4  # 5개 → 구분 빈 줄 4개
    assert "[5] 제목5" in out and "[6]" not in out and "제목6" not in out


@pytest.mark.parametrize("count", [1, 3])
async def test_result_count_follows_setting(count):
    out = await SearchService(FakeClient(results(10)), count).search("q")
    assert f"[{count}]" in out and f"[{count + 1}]" not in out


async def test_fewer_results_than_count_are_all_used():
    out = await SearchService(FakeClient(results(2)), 5).search("q")
    assert "[2]" in out and "[3]" not in out


async def test_no_results_returns_message_not_exception():
    assert await SearchService(FakeClient([]), 5).search("q") == NO_RESULTS


async def test_client_errors_propagate_for_caller_to_handle():
    """문자열로 바꾸는 건 호출하는 쪽(chat)의 일이다. 서비스는 검색 예외를 그대로 올린다."""
    err = SearchConnectionError("down")
    with pytest.raises(SearchConnectionError) as info:
        await SearchService(FakeClient(error=err), 5).search("q")
    assert info.value is err
