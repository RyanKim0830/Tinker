"""main.py 테스트: lifespan 이 로그를 설정하고, 종료할 때 HTTP 클라이언트를 모두 닫는지 본다."""
import logging

from src import main
from src.llm import client as llm_client
from src.search import client as search_client


async def test_lifespan_closes_llm_and_search_clients(monkeypatch):
    llm_client.get_llm_client()
    search_client.get_search_client()
    assert llm_client._http is not None and search_client._http is not None

    async with main.lifespan(main.app):
        pass

    assert llm_client._http is None and search_client._http is None  # 닫고 비웠다


async def test_lifespan_configures_logging_from_settings(monkeypatch):
    seen = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kw: seen.update(kw))
    monkeypatch.setenv("APP_LOG_LEVEL", "DEBUG")
    async with main.lifespan(main.app):
        pass
    assert seen["level"] == "DEBUG" and "%(name)s" in seen["format"]
