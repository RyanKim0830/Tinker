"""실제 SearXNG 를 대상으로 하는 통합 테스트.

실행:  docker compose -f searxng/compose.yaml up -d  로 SearXNG 를 먼저 띄운 뒤  pytest -m integration
기본 실행(pytest)에서는 제외된다 (pytest.ini 의 addopts).

서버가 없으면 skip 이 아니라 '실패'시킨다 (test_llama_server.py 와 같은 이유).
검색 결과는 매번 달라지므로 정확한 내용이 아니라 '성질'(결과가 있음, 형식, 개수 제한)만 검사한다.
"""
import re

import httpx
import pytest

from src.search.client import SearchClient
from src.search.config import SearchSettings
from src.search.service import SearchService

pytestmark = pytest.mark.integration

SETTINGS = SearchSettings(_env_file=None)  # 기본값(http://localhost:8888). 바꾸려면 SEARCH_SEARXNG_URL 환경변수로.


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as http:
        try:
            await http.get(SETTINGS.searxng_url, timeout=5)
        except httpx.TransportError:
            pytest.fail(f"SearXNG 가 {SETTINGS.searxng_url} 에 없다. docker compose -f searxng/compose.yaml up -d 를 먼저 실행할 것")
        yield SearchClient(http, SETTINGS)


async def test_client_gets_results_with_title_and_url(client):
    results = await client.search("서울 날씨")
    assert results
    assert all(r.title and r.url.startswith("http") for r in results)


async def test_service_returns_formatted_top_results(client):
    out = await SearchService(client, SETTINGS.result_count).search("서울 날씨")
    print("\n" + out)  # pytest -s 로 실제 출력을 볼 수 있다
    assert out.startswith("[1] ")
    assert re.search(r"^\[1\] .+ \(http\S+\)\n", out)  # "[번호] 제목 (URL)\n내용"
    assert f"[{SETTINGS.result_count + 1}]" not in out


async def test_service_limits_result_count(client):
    out = await SearchService(client, 2).search("python")
    assert "[2]" in out and "[3]" not in out
