"""chat 모듈의 FastAPI Depends 용 제공자.

LLM 클라이언트·검색 서비스는 주입받고, 대화 이력은 모듈 전역 하나를 모든 요청이 공유한다.
이력은 session_id 없이 프로세스 전체에서 하나다. 재시작하면 사라지는 것이 정상 동작이다.
"""
from fastapi import Depends

from src.chat.config import ChatSettings
from src.chat.service import ChatService
from src.llm import client as llm_client
from src.llm import dependencies as llm_dependencies
from src.message import Message
from src.search import dependencies as search_dependencies
from src.search import service as search_service

# 한 턴 전체(user, assistant(tool_calls), tool 결과, 최종 assistant)를 저장한다.
# 시스템 프롬프트는 저장하지 않고 호출 때마다 서비스가 맨 앞에 붙인다.
_history: list[Message] = []


def get_chat_service(
    llm: llm_client.LLMClient = Depends(llm_dependencies.get_llm_client),
    search: search_service.SearchService = Depends(search_dependencies.get_search_service),
) -> ChatService:
    return ChatService(llm, search, _history, ChatSettings())
