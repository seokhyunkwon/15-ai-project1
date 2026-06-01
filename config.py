# ================================
# config.py
# ================================

import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    NAVER_CLIENT_ID = (
        os.getenv("NAVER_CLIENT_ID") or ""
    ).strip()

    NAVER_CLIENT_SECRET = (
        os.getenv("NAVER_CLIENT_SECRET") or ""
    ).strip()

    KAKAO_REST_API_KEY = (
        os.getenv("KAKAO_REST_API_KEY") or ""
    ).strip()

    OPENAI_API_KEY = (
        os.getenv("OPENAI_API_KEY") or ""
    ).strip()
    GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY") or ""
    ).strip()   


CATEGORY_RULES = {
    "전기차": ["전기차", "ev", "배터리"],
    "자율주행": ["자율주행", "라이다", "ADAS"],
    "배터리": ["배터리", "2차전지"],
    "생산": ["생산", "공장", "라인"],
    "채용": ["채용", "신입", "인턴"],
}


DEFAULT_INDUSTRY_KEYWORDS = [
    "현대차",
    "기아",
    "자동차 부품",
    "전기차",
    "에스엘",
    "유라"
]