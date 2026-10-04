"""llama-server 클라이언트 (인프라 레이어).

역할: llama-server 의 OpenAI 호환 API(POST /v1/chat/completions)와 통신한다.
- 내부 형식(Message) ↔ 서버 JSON 형식 변환
- 연결 정보·샘플링 파라미터 관리 (llm/config.py)
- 외부 에러를 llm/exceptions.py 의 내부 예외로 변환
비즈니스 판단(대화 이력 관리, 프롬프트 구성 등)은 하지 않는다.
"""
import logging
import time
from dataclasses import dataclass
from typing import Literal

import httpx

from src.llm.config import LLMSettings
from src.llm.exceptions import LLMConnectionError, LLMResponseError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Message:
    """대화 한 줄. 서비스 레이어가 쓰는 내부 형식이며 HTTP 형식은 모른다."""

    role: Literal["system", "user", "assistant"]
    content: str


class LLMClient:
    def __init__(self, http: httpx.AsyncClient, settings: LLMSettings):
        # AsyncClient 는 밖에서 만들어 받는다 (연결 재사용, 테스트에서 가짜 transport 로 교체).
        self._http = http
        self._settings = settings

    async def chat(self, messages: list[Message]) -> str:
        """메시지 목록을 보내고 어시스턴트 답변 텍스트를 돌려준다. 스트리밍 없이 전체를 한 번에 받는다."""
        s = self._settings
        # 내부 형식 → 서버 요청 JSON. top_k 는 OpenAI 표준에는 없고 llama-server 확장 필드다.
        payload = {
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": s.temperature,
            "top_p": s.top_p,
            "top_k": s.top_k,
            "presence_penalty": s.presence_penalty,
            "stream": False,
        }
        logger.info("LLM 요청: messages=%d", len(messages))
        logger.debug("LLM payload: %s", payload)
        started = time.perf_counter()
        try:
            resp = await self._http.post(f"{s.base_url}/v1/chat/completions", json=payload, timeout=s.timeout)
        except httpx.TransportError as e:  # 연결 실패·타임아웃·전송 중 끊김
            raise LLMConnectionError(f"llama-server 에 연결하지 못했다 ({s.base_url}): {e!r}") from e

        logger.info("LLM 응답: status=%d, %.2fs", resp.status_code, time.perf_counter() - started)

        if resp.status_code != 200:
            raise LLMResponseError(f"llama-server 가 HTTP {resp.status_code} 를 돌려줬다: {resp.text[:200]}")

        # 서버 응답 JSON → 답변 텍스트. thinking 은 서버 옵션(--reasoning off)으로 끈 상태라
        # message.content 만 읽는다. 내용을 가공(제거·추정)하지 않는다.
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise LLMResponseError(f"응답 형식이 예상과 다르다: {resp.text[:200]}") from e


# --- FastAPI Depends 용 제공자 ---
# 프로세스 전체에서 AsyncClient 하나를 공유한다. 첫 호출 때 만들고, 서버 종료 시 close_llm_client() 로 닫는다.
_client: LLMClient | None = None
_http: httpx.AsyncClient | None = None


def get_llm_client() -> LLMClient:
    global _client, _http
    if _client is None:
        _http = httpx.AsyncClient()
        _client = LLMClient(_http, LLMSettings())
    return _client


async def close_llm_client() -> None:
    global _client, _http
    if _http is not None:
        await _http.aclose()
    _client = _http = None
