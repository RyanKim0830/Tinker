"""llm/dependencies.py 단위 테스트: 클라이언트를 프로세스에서 하나만 만들어 공유하고, 닫으면 비우는지 본다."""
from src.llm import dependencies


async def test_get_llm_client_is_shared_and_close_resets():
    await dependencies.close_llm_client()
    first = dependencies.get_llm_client()
    assert dependencies.get_llm_client() is first  # 프로세스 안에서 하나를 공유
    await dependencies.close_llm_client()
    assert dependencies.get_llm_client() is not first  # 닫으면 다음 호출 때 새로 만든다
    await dependencies.close_llm_client()
