"""애플리케이션 공통 설정.

모듈별 설정은 각 모듈에 둔다 (예: llm 은 src/llm/config.py). 여기에는 앱 전체(서버·CLI)가 쓰는 값만 둔다.
값은 환경변수(접두사 APP_) 또는 .env 에서 읽는다.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", extra="ignore")

    # FastAPI 서버가 듣는 주소. 개인용이라 기본은 로컬에서만 접근 가능하게 한다.
    host: str = "127.0.0.1"
    port: int = 8000
