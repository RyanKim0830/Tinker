"""공용 fixture."""
import pytest

from src.chat import service


@pytest.fixture(autouse=True)
def clean_history():
    """대화 이력은 모듈 전역 하나라 테스트끼리 새면 안 된다. 매 테스트 전후로 비운다."""
    service._history.clear()
    yield
    service._history.clear()
