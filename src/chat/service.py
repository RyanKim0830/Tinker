"""채팅 서비스 (비즈니스 레이어).

역할: 대화 이력을 보관하고, 질문마다 [시스템 프롬프트 + 이력 + 새 질문]을 LLM 에 보내 답을 받는다.
HTTP·llama-server 통신 방식은 모른다. LLM 은 LLMClient 를 통해서만 부른다.
"""
from fastapi import Depends

from src.llm.client import LLMClient, get_llm_client
from src.llm.exceptions import LLMConnectionError, LLMError
from src.message import Message

# 비즈니스 규칙: 비서의 역할과 말투
SYSTEM_PROMPT = "너는 사용자의 개인 비서다. 한국어로 짧게 답한다."

# 대화 이력. 프로세스 전체에서 하나(session_id 없음). 재시작하면 사라지는 것이 정상 동작이다.
# 시스템 프롬프트는 저장하지 않고 호출 때마다 맨 앞에 붙인다.
_history: list[Message] = []


class ChatUnavailableError(Exception):
    """LLM 서버에 연결할 수 없어 답을 못 만든다. (프레젠테이션 레이어가 '서비스 불가'로 포장)"""


class ChatFailedError(Exception):
    """LLM 서버가 이상한 응답을 줘서 답을 못 만든다. (프레젠테이션 레이어가 '상위 서버 오류'로 포장)"""


class ChatService:
    def __init__(self, llm: LLMClient, history: list[Message]):
        self._llm = llm
        self._history = history

    async def chat(self, query: str) -> str:
        user = Message("user", query)
        messages = [Message("system", SYSTEM_PROMPT), *self._history, user]
        # llm 의 예외를 서비스 예외로 바꿔 올린다: 윗 레이어가 llm 모듈을 몰라도 되게 한다.
        try:
            reply = await self._llm.chat(messages)
        except LLMConnectionError as e:
            raise ChatUnavailableError("LLM 서버에 연결할 수 없다") from e
        except LLMError as e:
            raise ChatFailedError("LLM 서버 응답이 정상이 아니다") from e
        # 답을 받은 뒤에만 이력에 넣는다. 실패한 턴은 이력에 남지 않는다.
        self._history.extend([user, Message("assistant", reply)])
        return reply


def get_chat_service(llm: LLMClient = Depends(get_llm_client)) -> ChatService:
    """FastAPI Depends 용. LLM 클라이언트는 주입받고, 이력은 모듈 전역 하나를 공유한다."""
    return ChatService(llm, _history)
