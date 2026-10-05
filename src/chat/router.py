"""POST /chat 라우터 (프레젠테이션 레이어).

역할: 요청 검증은 schemas 에 맡기고, 서비스를 호출하고, 서비스 예외를 HTTP 상태 코드로 포장한다.
비즈니스 로직은 두지 않는다. 서비스(chat/service.py)만 알고, llm 모듈은 모른다.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

from src.chat.exceptions import ChatFailedError, ChatUnavailableError
from src.chat.schemas import ChatRequest, ChatResponse
from src.chat.service import ChatService, get_chat_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, service: ChatService = Depends(get_chat_service)) -> ChatResponse:
    try:
        reply = await service.chat(req.query)
    except ChatUnavailableError:
        logger.exception("chat 실패: LLM 서버 연결 불가")
        # LLM 서버가 꺼져 있거나 닿지 않음 → 503 Service Unavailable
        raise HTTPException(status_code=503, detail="LLM 서버에 연결할 수 없다")
    except ChatFailedError:
        logger.exception("chat 실패: LLM 서버 응답 이상")
        # LLM 서버가 정상이 아닌 응답을 줌 → 502 Bad Gateway
        raise HTTPException(status_code=502, detail="LLM 서버 응답이 정상이 아니다")
    return ChatResponse(reply=reply)
