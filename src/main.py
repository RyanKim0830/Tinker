"""FastAPI 앱 진입점 (프레젠테이션 레이어).

실행: python -m src.main   (또는 uvicorn src.main:app --port 8000)
"""
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from src.chat.router import router as chat_router
from src.config import AppSettings
from src.llm.client import close_llm_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=AppSettings().log_level,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    )
    yield
    # 서버 종료 시 LLM 클라이언트의 HTTP 연결을 닫는다.
    await close_llm_client()


app = FastAPI(title="Tinker", lifespan=lifespan)
app.include_router(chat_router)


if __name__ == "__main__":
    settings = AppSettings()
    uvicorn.run(app, host=settings.host, port=settings.port)
