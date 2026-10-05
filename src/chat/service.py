"""채팅 서비스 (비즈니스 레이어).

역할: 대화 이력을 보관하고, 질문마다 툴 콜링 루프(ReAct)를 돌려 답을 만든다.
  LLM 호출 → 툴 호출이 있으면 전부 실행해 결과를 붙이고 다시 LLM 호출 → 툴 호출이 없으면 그 답이 최종 답.
LLM 은 LLMClient, 검색은 SearchService 를 통해서만 부른다. 두 패키지는 서로를 모르고 이 서비스만 둘을 엮는다.
HTTP·llama-server·SearXNG 통신 방식은 모른다.
"""
import logging
from collections.abc import Callable
from datetime import date

from fastapi import Depends

from src.chat import tools
from src.chat.config import ChatSettings
from src.llm import client as llm_client
from src.llm import exceptions as llm_exceptions
from src.message import Message
from src.search import service as search_service

logger = logging.getLogger(__name__)

# 비즈니스 규칙: 비서의 역할과 말투
BASE_PROMPT = "너는 Ai 에이전트 Tinker 이다. 사용자와 친한 사이며, 아재개그를 좋아한다."
# 비즈니스 규칙: 검색 결과가 있을 때의 태도
SEARCH_PROMPT = "검색 결과가 있으면 그것을 근거로 답한다."


def build_system_prompt(today: date) -> str:
    """시스템 프롬프트 = 기존 문구 + 오늘 날짜 + 검색 결과 사용 규칙. LLM 은 오늘 날짜를 모르므로 매번 넣는다."""
    return f"{BASE_PROMPT} 오늘 날짜는 {today.isoformat()}이다. {SEARCH_PROMPT}"


# 대화 이력. 프로세스 전체에서 하나(session_id 없음). 재시작하면 사라지는 것이 정상 동작이다.
# 한 턴 전체(user, assistant(tool_calls), tool 결과, 최종 assistant)를 저장한다.
# 시스템 프롬프트는 저장하지 않고 호출 때마다 맨 앞에 붙인다.
_history: list[Message] = []


class ChatUnavailableError(Exception):
    """LLM 서버에 연결할 수 없어 답을 못 만든다. (프레젠테이션 레이어가 '서비스 불가'로 포장)"""


class ChatFailedError(Exception):
    """LLM 서버가 이상한 응답을 줘서 답을 못 만든다. (프레젠테이션 레이어가 '상위 서버 오류'로 포장)"""


class ChatService:
    def __init__(
        self,
        llm: llm_client.LLMClient,
        search: search_service.SearchService,
        history: list[Message],
        settings: ChatSettings,
        today: Callable[[], date] = date.today,  # 테스트에서 날짜를 고정하려고 주입받는다
    ):
        self._llm = llm
        self._search = search
        self._history = history
        self._settings = settings
        self._today = today

    async def chat(self, query: str) -> str:
        # 이번 턴에서 새로 생기는 메시지. 턴이 끝까지 성공했을 때만 이력에 합친다.
        turn = [Message("user", query)]
        system = Message("system", build_system_prompt(self._today()))
        last_round = self._settings.max_tool_rounds

        for round_no in range(1, last_round + 1):
            # 마지막 왕복은 tools 를 빼서, 더 부르지 못하고 지금까지의 결과로 답하게 한다.
            offer_tools = round_no < last_round
            reply = await self._call_llm([system, *self._history, *turn], tools.TOOLS if offer_tools else None)
            logger.info("round %d/%d content=%r tool_calls=%s", round_no, last_round, reply.content, reply.tool_calls)

            if not reply.tool_calls or not offer_tools:
                if reply.tool_calls:  # tools 를 안 줬는데 온 호출은 실행할 수 없고, 짝이 없는 호출을 이력에 남기면 안 된다.
                    logger.warning("tools 없이 부른 마지막 왕복에 tool_calls 가 왔다(무시): %s", reply.tool_calls)
                final = Message("assistant", reply.content)
                if not final.content:
                    logger.warning("최종 답의 content 가 비어 있다 (round %d/%d). 빈 문자열로 답한다.", round_no, last_round)
                # 턴 전체를 이력에 저장한다: 후속 질문에서 검색 원문을 참조할 수 있게.
                self._history.extend([*turn, final])
                return final.content

            # 툴 호출이 여러 개면 순서대로 전부 실행한다. assistant(tool_calls)와 tool 결과는 항상 짝으로 넣는다.
            turn.append(reply)
            for call in reply.tool_calls:
                result = await tools.run_tool(call, self._search)
                turn.append(Message("tool", result, tool_call_id=call.id))

        raise AssertionError("unreachable: 마지막 왕복은 항상 위에서 return 한다")  # max_tool_rounds >= 1 (ChatSettings)

    async def _call_llm(self, messages: list[Message], offered_tools: list[dict] | None) -> Message:
        # llm 의 예외를 서비스 예외로 바꿔 올린다: 윗 레이어가 llm 모듈을 몰라도 되게 한다.
        # 실패하면 이력에는 아무것도 남기지 않는다(턴이 끝까지 가야 저장).
        try:
            return await self._llm.chat(messages, offered_tools)
        except llm_exceptions.LLMConnectionError as e:
            raise ChatUnavailableError("LLM 서버에 연결할 수 없다") from e
        except llm_exceptions.LLMError as e:
            raise ChatFailedError("LLM 서버 응답이 정상이 아니다") from e


def get_chat_service(
    llm: llm_client.LLMClient = Depends(llm_client.get_llm_client),
    search: search_service.SearchService = Depends(search_service.get_search_service),
) -> ChatService:
    """FastAPI Depends 용. LLM 클라이언트·검색 서비스는 주입받고, 이력은 모듈 전역 하나를 공유한다."""
    return ChatService(llm, search, _history, ChatSettings())
