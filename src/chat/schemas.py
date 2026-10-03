"""POST /chat 요청·응답 형식 (프레젠테이션 레이어).

여기서 정의한 형식에 맞지 않는 요청은 FastAPI 가 422 로 거절한다.
"""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    # 빈 문자열은 거절한다. 공백만 있는 문자열은 막지 않는다 (판단을 넣지 않는다).
    query: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
