"""chat 모듈 설정 (비즈니스 레이어).

툴 콜링 루프의 규칙 값을 코드에서 빼서 한 곳에서 관리한다. (코드에 판단을 넣지 않는다: ADR-0013)
값은 환경변수(접두사 CHAT_) 또는 .env 에서 읽고, 없으면 아래 기본값을 쓴다.
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ChatSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHAT_", env_file=".env", extra="ignore")

    # 질문 하나에 LLM 을 부르는 최대 횟수(왕복). 호출한 툴 개수가 아니라 LLM 왕복으로 센다.
    # 마지막 왕복은 tools 를 빼고 보내서 그때까지의 결과로 답하게 한다. 1 이면 툴 없이 항상 바로 답한다.
    max_tool_rounds: int = Field(default=2, ge=1)
