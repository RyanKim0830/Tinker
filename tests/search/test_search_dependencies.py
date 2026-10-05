"""search/dependencies.py 단위 테스트: 클라이언트는 하나를 공유하고, 서비스는 요청마다 새로 만드는지 본다."""
from src.search import dependencies
from src.search.config import SearchSettings


async def test_get_search_client_is_shared_and_close_resets():
    await dependencies.close_search_client()
    first = dependencies.get_search_client()
    assert dependencies.get_search_client() is first  # 프로세스 안에서 하나를 공유
    await dependencies.close_search_client()
    assert dependencies.get_search_client() is not first  # 닫으면 다음 호출 때 새로 만든다
    await dependencies.close_search_client()


async def test_get_search_service_is_new_per_call_but_shares_client():
    await dependencies.close_search_client()
    client = dependencies.get_search_client()
    first = dependencies.get_search_service(client)
    second = dependencies.get_search_service(client)
    assert first is not second  # 서비스는 요청마다 새로 만든다
    assert first._client is second._client is client  # 클라이언트는 공유한다
    assert first._result_count == SearchSettings().result_count  # 결과 개수는 설정에서 읽는다
    await dependencies.close_search_client()
