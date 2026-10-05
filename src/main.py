"""FastAPI 앱 진입점 (프레젠테이션 레이어).

실행: python -m src.main   (또는 uvicorn src.main:app --port 8000)
"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.chat.router import router as chat_router
from src.config import AppSettings
from src.llm import client as llm_client
from src.search import client as search_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 표준 logging 설정. 각 모듈은 logging.getLogger(__name__) 로 남기고, 출력 형식·수준은 여기서 한 번만 정한다.
    logging.basicConfig(
        level=AppSettings().log_level,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    )
    yield
    # 서버 종료 시 LLM·검색 클라이언트의 HTTP 연결을 닫는다.
    await llm_client.close_llm_client()
    await search_client.close_search_client()


app = FastAPI(title="Tinker", lifespan=lifespan)
app.include_router(chat_router)


if __name__ == "__main__":
    settings = AppSettings()
    uvicorn.run(app, host=settings.host, port=settings.port)
