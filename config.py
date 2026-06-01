import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_INDUSTRY_KEYWORDS = [
    "자동차 부품",
    "전장 부품",
    "전기차",
    "공급망",
]

CATEGORY_RULES = {
    "자동차 부품": ["자동차 부품", "부품", "1차 협력", "모듈", "프레임", "차체"],
    "전장 부품": ["전장", "전자", "ECU", "반도체", "센서", "와이어링", "계기판"],
    "전기차": ["전기차", "EV", "배터리", "충전", "수소", "하이브리드", "모터"],
    "공급망": ["공급망", "물류", "조달", "납품", "수급", "리콜", "원자재"],
}


class Config:
    NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
    NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
    KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    FIXED_COMPANIES = {
        "현대자동차": "https://www.hyundai.com",
        "서연이화": "https://seoyoneh.com/",
        "화신": "http://hsp.hwashin.co.kr/kr/main.do",
        "세원정공": "https://www.se-won.com/client/contents/recruit/talent_type.html",
        "성우하이텍": "https://www.swhitech.com/kr/index.php?pCode=hrmVal",
        "대원강업": "http://www.dwku.com/",
        "에스엘": "https://www.slworld.com/",
        "우진산업": "https://www.wamc.co.kr/",
        "THN": "https://www.th-net.co.kr/",
    }

    LOCAL_MODEL_PATH = os.getenv(
        "LOCAL_MODEL_PATH",
        str(BASE_DIR / "models" / "Llama-3-Korean-Bllossom-8B-Q4_K_M.gguf"),
    )
    USE_GPU = os.getenv("USE_GPU", "true").lower() in {"1", "true", "yes", "y"}
