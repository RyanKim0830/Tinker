"""터미널 챗 클라이언트.

FastAPI 서버(POST /chat)에 질문을 보내고 답을 출력한다. 대화 이력은 서버가 들고 있으므로
이 CLI 는 이력을 보관하지 않는다. 서버를 재시작하면 대화도 초기화된다.

사용: (서버 실행 중에) python cli.py      종료: /exit 또는 Ctrl+D
"""
import asyncio
from collections.abc import Awaitable, Callable

import httpx

from src.config import AppSettings

EXIT_COMMAND = "/exit"
# 한 질문에 서버가 LLM 을 최대 2번(각 120초), 그 사이에 검색(15초)을 하므로 그 합(약 255초)보다 넉넉히 잡는다.
TIMEOUT = 450.0


async def ask(http: httpx.AsyncClient, base_url: str, query: str) -> str:
    """POST /chat 한 번. 연결 실패(httpx.TransportError)·HTTP 오류(httpx.HTTPStatusError)는 그대로 올린다."""
    query = query.encode("utf-8", errors="replace").decode("utf-8")
    resp = await http.post(f"{base_url}/chat", json={"query": query}, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()["reply"]


async def chat_loop(
    http: httpx.AsyncClient,
    base_url: str,
    read_line: Callable[[], Awaitable[str]],
    write: Callable[[str], None] = print,
) -> None:
    """한 줄 읽기 → 서버에 전송 → 답 출력을 반복한다. 입출력을 주입받아 테스트할 수 있다."""
    write(f"Tinker 에 연결합니다 ({base_url}). 종료: {EXIT_COMMAND} 또는 Ctrl+D")
    while True:
        try:
            line = await read_line()
        except EOFError:
            return
        if line.strip() == EXIT_COMMAND:
            return
        if not line.strip():  # 빈 입력은 서버가 422 로 거절하므로 보내지 않는다
            continue
        try:
            write(await ask(http, base_url, line))
        except httpx.TransportError:
            write(f"[오류] 서버에 연결할 수 없다. 먼저 'python -m src.main' 으로 서버를 실행했는지 확인할 것 ({base_url})")
        except httpx.HTTPStatusError as e:
            write(f"[오류] 서버가 HTTP {e.response.status_code} 를 돌려줬다: {e.response.text}")


async def main() -> None:
    s = AppSettings()
    base_url = f"http://{s.host}:{s.port}"

    async def read_line() -> str:
        # input() 은 막히는 호출이라 별도 스레드에서 실행한다 (이벤트 루프를 막지 않기 위해)
        return await asyncio.to_thread(input, "> ")

    async with httpx.AsyncClient() as http:
        await chat_loop(http, base_url, read_line)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
