"""search 모듈 설정 (인프라 레이어).

SearXNG 연결 정보와 검색 결과 개수를 한 곳에서 관리한다.
값은 환경변수(접두사 SEARCH_) 또는 .env 에서 읽고, 없으면 아래 기본값을 쓴다.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class SearchSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SEARCH_", env_file=".env", extra="ignore")

    # SearXNG 주소 (searxng/compose.yaml 이 호스트의 8888 로 연다)
    searxng_url: str = "http://localhost:8888"
    # 검색 요청 하나를 기다리는 시간. 초 단위. 여러 엔진이 응답할 때까지 SearXNG 가 기다리므로 넉넉히 잡는다.
    timeout: float = 15.0
    # LLM 에 넘기는 검색 결과(스니펫) 개수. 상위 N개를 쓴다.
    result_count: int = 5
