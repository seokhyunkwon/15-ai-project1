import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# 산업 키워드 기본값 (쉼표로 추가 입력 가능)
DEFAULT_INDUSTRY_KEYWORDS = [
    "자동차 부품",
    "전장부품",
    "전기차",
    "공급망",
]

# 키워드 → 카테고리 분류 규칙
CATEGORY_RULES = {
    "자동차 부품": ["자동차 부품", "부품", "1차 협력", "모듈", "프레스"],
    "전장 부품": ["전장", "전자", "ECU", "반도체", "센서", "와이어링"],
    "전기차": ["전기차", "EV", "배터리", "충전", "수소", "하이브리드"],
    "공급망": ["공급망", "물류", "조달", "납품", "수급", "리콜"],
}


class Config:
    NAVER_CLIENT_ID = (os.getenv("NAVER_CLIENT_ID") or "").strip()
    NAVER_CLIENT_SECRET = (os.getenv("NAVER_CLIENT_SECRET") or "").strip()
    KAKAO_REST_API_KEY = (
        os.getenv("KAKAO_REST_API_KEY") or os.getenv("KAKAO_API_KEY") or ""
    ).strip()
