"""search 모듈 전용 예외.

외부(SearXNG)에서 난 에러를 httpx 예외 그대로 올리지 않고 이 예외로 바꿔서 올린다.
윗 레이어가 httpx 를 몰라도 되게 하기 위해서다. (llm/exceptions.py 와 같은 구조)
"""


class SearchError(Exception):
    """search 모듈에서 올라오는 모든 예외의 부모."""


class SearchConnectionError(SearchError):
    """SearXNG 에 연결하지 못했거나 응답을 기다리다 끊김 (서버 꺼짐, 포트 오류, 타임아웃 등)."""


class SearchResponseError(SearchError):
    """서버에는 닿았지만 응답이 정상이 아님 (HTTP 오류 상태, 예상과 다른 JSON 형식)."""
