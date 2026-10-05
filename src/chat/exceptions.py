"""chat 모듈 전용 예외.

서비스가 llm 모듈의 예외를 이 예외로 바꿔서 올린다. 윗 레이어(router)가 llm 모듈을 몰라도 되게 하기 위해서다.
(llm/exceptions.py, search/exceptions.py 와 같은 구조)
"""


class ChatUnavailableError(Exception):
    """LLM 서버에 연결할 수 없어 답을 못 만든다. (프레젠테이션 레이어가 '서비스 불가'로 포장)"""


class ChatFailedError(Exception):
    """LLM 서버가 이상한 응답을 줘서 답을 못 만든다. (프레젠테이션 레이어가 '상위 서버 오류'로 포장)"""
