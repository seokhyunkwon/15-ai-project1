from __future__ import annotations

import re

from config import DEFAULT_INDUSTRY_KEYWORDS, HYUNDAI_KIA_FIRST_TIER_VENDORS


CAREER_INTENT_TERMS = {
    "자동차",
    "자동차부품",
    "부품",
    "전장",
    "전장부품",
    "전기차",
    "배터리",
    "공급망",
    "품질",
    "품질관리",
    "생산",
    "생산기술",
    "생산관리",
    "제조",
    "제조업",
    "반도체",
    "센서",
    "물류",
    "조달",
    "채용",
    "채용공고",
    "면접",
    "복지",
    "복리후생",
    "근무제도",
    "기업",
    "기업정보",
    "산업",
    "직무",
    "뉴스",
}

COMPANY_NAME_HINTS = {
    "산업",
    "전자",
    "전기",
    "정공",
    "공업",
    "금속",
    "화학",
    "기계",
    "모터스",
    "오토",
    "테크",
    "시스템",
    "솔루션",
    "코리아",
    "엔지니어링",
    "로보틱스",
    "소재",
    "에너지",
    "건설",
    "중공업",
    "물산",
    "상사",
    "홀딩스",
    "그룹",
    "바이오",
    "제약",
}

PUBLIC_COMPANY_ALIASES = {
    "현대",
    "현대자동차",
    "기아",
    "아진",
    "아진산업",
    "삼성",
    "삼성전자",
    "LG",
    "엘지",
    "SK",
    "네이버",
    "카카오",
    "포스코",
    "한화",
    "롯데",
    "CJ",
    "GS",
    "HD현대",
    "Tesla",
    "OpenAI",
    "Naver",
    "Kakao",
}

LATIN_COMPANY_MARKERS = {
    "auto",
    "tech",
    "motor",
    "motors",
    "mobility",
    "semiconductor",
    "energy",
    "robotics",
    "bio",
    "korea",
}


def normalize_search_query(value: str) -> str:
    normalized = re.sub(r"[\s\W_]+", "", (value or "").lower(), flags=re.UNICODE)
    return normalized.translate(str.maketrans({
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
    }))


def validate_search_query(value: str) -> str:
    normalized = normalize_search_query(value)
    if not normalized:
        return "검색어를 입력해 주세요."
    if len(normalized) < 2:
        return "검색어가 너무 짧습니다. 회사명, 산업명, 직무명을 2글자 이상 입력해 주세요."
    if _has_career_intent(normalized):
        return ""
    if _looks_like_company_name(normalized):
        return ""
    return "취업 뉴스 분석에 적합한 검색어인지 판단하기 어렵습니다. 정확한 회사명 또는 산업·직무 키워드로 검색해 주세요."


def _has_career_intent(normalized: str) -> bool:
    return any(term in normalized for term in _normalized_terms(CAREER_INTENT_TERMS))


def _looks_like_company_name(normalized: str) -> bool:
    known_names = _normalized_terms(
        set(HYUNDAI_KIA_FIRST_TIER_VENDORS) | PUBLIC_COMPANY_ALIASES
    )
    if normalized in known_names:
        return True
    if any(hint in normalized for hint in _normalized_terms(COMPANY_NAME_HINTS)):
        return True

    hangul = re.sub(r"[^가-힣]", "", normalized)
    latin = re.sub(r"[^a-z0-9]", "", normalized)
    if latin and not hangul:
        return normalized in known_names or any(
            marker in normalized for marker in LATIN_COMPANY_MARKERS
        )
    return len(hangul) >= 4


def _normalized_terms(values: set[str] | list[str]) -> set[str]:
    return {
        normalize_search_query(value)
        for value in [*values, *DEFAULT_INDUSTRY_KEYWORDS]
        if value
    }
