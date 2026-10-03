"""llm 모듈 설정 (인프라 레이어).

llama-server 연결 정보와 샘플링 파라미터를 한 곳에서 관리한다.
값은 환경변수(접두사 LLM_) 또는 .env 에서 읽고, 없으면 아래 기본값을 쓴다.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_", env_file=".env", extra="ignore")

    # llama-server 주소 (scripts/llama-server.sh 가 8080 으로 띄운다)
    base_url: str = "http://localhost:8080"
    # 전체 응답을 한 번에 받으므로 생성이 끝날 때까지 기다리는 시간. 초 단위.
    timeout: float = 120.0

    # Qwen3.5 모델 카드의 non-thinking 일반 작업 권장 샘플링 값
    temperature: float = 0.7
    top_p: float = 0.8
    top_k: int = 20
    presence_penalty: float = 1.5
