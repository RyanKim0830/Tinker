"""LLM 에 제공하는 툴 목록과 실행 (비즈니스 레이어).

- TOOLS: LLM 에 보내는 툴 정의 (OpenAI 형식). 이름·설명·인자가 LLM 이 툴을 부를지 말지 정하는 근거다.
- run_tool: LLM 이 요청한 ToolCall 하나를 실행해 '결과 문자열'로 돌려준다.

툴 실행의 실패(잘못된 호출, 검색 실패)는 예외로 올리지 않고 문자열로 돌려준다. LLM 이 그 내용을 보고 다시 시도하거나
사정을 설명하며 답하게 하기 위해서다. 서비스는 검색 문제로 죽으면 안 된다.
search 패키지만 알고 llm 패키지는 모른다. (ToolCall 은 공용 형식 src/message.py)
"""
import json
import logging
from collections.abc import Awaitable, Callable

from src.message import ToolCall
from src.search import exceptions as search_exceptions
from src.search import service as search_service

logger = logging.getLogger(__name__)

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "웹을 검색해 결과 목록(제목, URL, 내용 일부)을 돌려준다. 최신 정보나 확실히 모르는 사실이 필요할 때만 쓴다.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "검색어"}},
            "required": ["query"],
        },
    },
}

TOOLS = [WEB_SEARCH_TOOL]


async def _web_search(args: dict, search: search_service.SearchService) -> str:
    """web_search 툴. query 가 없거나 문자열이 아니면 오류 문자열을 돌려준다."""
    query = args.get("query")
    if not isinstance(query, str):
        return "오류: query 인자가 없거나 문자열이 아니다. web_search 는 문자열 query 가 필요하다."
    try:
        return await search.search(query)
    except search_exceptions.SearchConnectionError as e:
        logger.warning("검색 실패(연결): %s", e)
        return "검색 실패: 검색 서버에 연결할 수 없다."
    except search_exceptions.SearchError as e:
        logger.warning("검색 실패(응답): %s", e)
        return "검색 실패: 검색 서버 응답이 정상이 아니다."


# 툴 이름 → 실행 함수. TOOLS 에 정의를 더하면 여기에도 같은 이름으로 넣는다.
_HANDLERS: dict[str, Callable[[dict, search_service.SearchService], Awaitable[str]]] = {
    "web_search": _web_search,
}


async def run_tool(call: ToolCall, search: search_service.SearchService) -> str:
    """ToolCall 하나를 실행해 결과 문자열을 돌려준다. 잘못된 호출도 예외가 아니라 오류 문자열로 돌려준다."""
    logger.info("툴 호출 name=%s arguments=%r", call.name, call.arguments)
    handler = _HANDLERS.get(call.name)
    if handler is None:
        logger.warning("등록되지 않은 툴: %s", call.name)
        return f"오류: 등록되지 않은 툴이다: {call.name}. 사용할 수 있는 툴: {', '.join(_HANDLERS)}"
    try:
        args = json.loads(call.arguments)
    except ValueError:
        logger.warning("arguments 가 JSON 이 아님: %r", call.arguments)
        return f"오류: arguments 가 JSON 이 아니다: {call.arguments}"
    if not isinstance(args, dict):
        logger.warning("arguments 가 JSON 객체가 아님: %r", call.arguments)
        return f"오류: arguments 는 JSON 객체여야 한다: {call.arguments}"
    return await handler(args, search)
