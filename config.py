import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# 산업 키워드 기본값(쉼표로 추가 입력 가능)
DEFAULT_INDUSTRY_KEYWORDS = [
    "자동차 부품",
    "전장 부품",
    "전기차",
    "공급망",
]

# 키워드 기반 카테고리 분류 규칙
CATEGORY_RULES = {
    "자동차 부품": ["자동차 부품", "부품", "1차 협력", "모듈", "프레임"],
    "전장 부품": ["전장", "전자", "ECU", "반도체", "센서", "와이어링"],
    "전기차": ["전기차", "EV", "배터리", "충전", "수소", "하이브리드"],
    "공급망": ["공급망", "물류", "조달", "납품", "수급", "리콜"],
}

# 현대/기아 1차 협력사(HKMC) 참여 기업 추천 목록
HYUNDAI_KIA_FIRST_TIER_VENDORS = [
    "영진정공",
    "네오오토",
    "동보",
    "지엠비코리아",
    "현대성우캐스팅",
    "현대케피코",
    "현대파워텍",
    "경창산업",
    "남양공업",
    "대승",
    "인팩",
    "리한",
    "코리아에프티",
    "현대성우메탈",
    "센트랄",
    "현대위아",
    "에스엘",
    "금강화학",
    "대원산업",
    "동아화성",
    "서연이화",
    "아성프라텍",
    "아진산업",
    "삼송",
    "두올",
    "두올산업",
    "세동",
    "LS오토모티브",
    "서연전자",
    "유라코퍼레이션",
    "인팩일렉스",
    "만도",
    "티에이치엔",
    "현대성우쏠라이트",
    "동원금속",
    "베바스토동희",
    "성우하이텍",
    "세원정공",
    "금창",
    "경신",
    "두원공조",
    "세명테크",
    "위너콤",
    "트래닛",
    "평화산업",
]


class Config:
    NAVER_CLIENT_ID = (os.getenv("NAVER_CLIENT_ID") or "").strip()
    NAVER_CLIENT_SECRET = (os.getenv("NAVER_CLIENT_SECRET") or "").strip()
    KAKAO_REST_API_KEY = (
        os.getenv("KAKAO_REST_API_KEY") or os.getenv("KAKAO_API_KEY") or ""
    ).strip()
