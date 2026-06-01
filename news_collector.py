import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import requests
from bs4 import BeautifulSoup

from ai_analyzer import analyze_news_batch
from career_data import get_company_profile
from config import Config


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news.json"
ANALYSIS_CACHE_FILE = DATA_DIR / "analysis_cache.json"
ANALYSIS_CACHE_VERSION = "v9-stable-readable"


COMPANY_SEARCH_HINTS = {
    "에스엘": "자동차 헤드램프 램프 부품",
    "SL": "자동차 헤드램프 램프 부품",
    "현대차": "자동차 모빌리티",
    "현대모비스": "자동차 부품 전장 모듈",
    "기아": "자동차 모빌리티 전기차",
    "신라": "자동차 부품 전장",
    "HL만도": "자동차 부품 제동 조향 자율주행",
    "THN": "자동차 와이어링 하네스 전장 부품",
    "티에이치엔": "자동차 와이어링 하네스 전장 부품",
}


COMPANY_ALIASES = {
    "에스엘": ["에스엘", "SL", "S L"],
    "SL": ["에스엘", "SL", "S L"],
    "현대차": ["현대차", "현대자동차"],
    "현대모비스": ["현대모비스", "모비스", "Hyundai Mobis"],
    "기아": ["기아", "기아차"],
    "신라": ["신라", "신라코퍼레이션"],
    "HL만도": ["HL만도", "만도", "Mando"],
    "THN": ["THN", "티에이치엔", "티에이치엔 주식회사"],
    "티에이치엔": ["THN", "티에이치엔", "티에이치엔 주식회사"],
}


INDUSTRY_TERMS = [
    "자동차",
    "모빌리티",
    "전기차",
    "자율주행",
    "부품",
    "전장",
    "헤드램프",
    "램프",
    "라이다",
    "ADAS",
    "배터리",
    "차량",
    "완성차",
    "생산",
    "공장",
    "품질",
    "R&D",
    "연구개발",
    "채용",
    "신입",
    "인턴",
    "실적",
    "투자",
    "수주",
    "와이어링",
    "하네스",
    "커넥터",
]


UNRELATED_TERMS = [
    "의료",
    "병원",
    "환자",
    "진료",
    "수술",
    "소송",
    "법원",
    "경찰",
    "경매",
    "부동산",
    "아파트",
    "분양",
    "연예",
    "스포츠",
]


STOPWORDS = {
    "기자",
    "뉴스",
    "관련",
    "통해",
    "지난",
    "이번",
    "최근",
    "오늘",
    "내년",
    "올해",
    "대해",
    "위해",
    "있는",
    "없는",
    "한다",
    "했다",
    "된다",
    "보다",
    "밝혔다",
    "말했다",
    "따르면",
    "그리고",
    "하지만",
    "또한",
    "에서",
    "으로",
    "에게",
    "까지",
    "부터",
}


SIMILARITY_THRESHOLD = 0.58


def strip_html(text):
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def normalize_text(text):
    return (text or "").replace(" ", "").lower()


def tokenize_news_text(title, summary):
    text = f"{title} {summary}".lower()
    tokens = re.findall(r"[0-9a-zA-Z가-힣]+", text)

    return {
        token
        for token in tokens
        if len(token) >= 2 and token not in STOPWORDS
    }


def similarity_ratio(tokens_a, tokens_b):
    if not tokens_a or not tokens_b:
        return 0

    overlap = len(tokens_a & tokens_b)
    smaller = min(len(tokens_a), len(tokens_b))
    return overlap / smaller


def is_similar_to_existing(title, summary, fingerprints):
    current = tokenize_news_text(title, summary)

    for saved in fingerprints:
        if similarity_ratio(current, saved) >= SIMILARITY_THRESHOLD:
            return True

    fingerprints.append(current)
    return False


def get_keyword_aliases(keyword):
    profile = get_company_profile(keyword)
    aliases = profile.get("aliases", [])
    return aliases or COMPANY_ALIASES.get(keyword, [keyword])


def build_search_query(keyword):
    profile = get_company_profile(keyword)
    profile_hint = profile.get("search_hint", "")

    if profile_hint:
        return f"{keyword} {profile_hint}"

    hint = COMPANY_SEARCH_HINTS.get(keyword, "")
    return f"{keyword} {hint}".strip()


def contains_any(text, terms):
    normalized = normalize_text(text)
    return any(normalize_text(term) in normalized for term in terms if term)


def is_relevant_news(keyword, title, summary):
    text = f"{title} {summary}"
    aliases = get_keyword_aliases(keyword)
    profile = get_company_profile(keyword)
    industry_terms = list(set(INDUSTRY_TERMS + profile.get("industry_terms", [])))

    has_company = contains_any(text, aliases)
    has_industry = contains_any(text, industry_terms)
    has_unrelated = contains_any(text, UNRELATED_TERMS)

    if not has_company:
        return False

    if has_unrelated and not has_industry:
        return False

    return True


def make_profile_key(user_profile):
    if not user_profile:
        return "no-profile"

    parts = [
        user_profile.get("major", ""),
        user_profile.get("target_job", ""),
        user_profile.get("certificates", ""),
        user_profile.get("experience", ""),
        user_profile.get("strengths", ""),
    ]

    return normalize_text("|".join(parts)) or "no-profile"


def make_cache_key(link, title, keyword="", user_profile=None):
    base = link or normalize_text(title)
    return f"{ANALYSIS_CACHE_VERSION}::{normalize_text(keyword)}::{make_profile_key(user_profile)}::{base}"


def read_analysis_cache():
    if not ANALYSIS_CACHE_FILE.exists():
        return {}

    try:
        with open(ANALYSIS_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_analysis_cache(cache):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(ANALYSIS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def empty_analysis(message, status="skipped"):
    return {
        "analysis_status": status,
        "ai_summary": message,
        "related_jobs": message,
        "spec_activities": message,
        "portfolio_ideas": message,
        "talent_fit": message,
        "cover_letter_direction": message,
        "cover_letter_draft": message,
        "interview_questions": message,
        "answer_direction": message,
        "profile_gap": message,
        "career_strategy": message,
        "ai_analysis": message,
    }


def is_failed_analysis(analysis):
    if not analysis:
        return True

    if analysis.get("analysis_status") in {"failed", "skipped"}:
        return True

    text = " ".join(str(analysis.get(key, "")) for key in ("ai_summary", "ai_analysis"))
    return "AI 배치 분석 실패" in text or "AI 분석 결과 누락" in text or "Request timed out" in text


def build_item(
    keyword,
    company_name,
    title,
    summary,
    link,
    source,
    publisher,
    published,
    analysis,
):
    return {
        "keyword": keyword,
        "company_name": company_name,
        "title": title,
        "summary": summary,
        "link": link,
        "source": source,
        "publisher": publisher,
        "published": published,
        "analysis_status": analysis.get("analysis_status", "ok"),
        "ai_summary": analysis.get("ai_summary", ""),
        "related_jobs": analysis.get("related_jobs", ""),
        "spec_activities": analysis.get("spec_activities", ""),
        "portfolio_ideas": analysis.get("portfolio_ideas", ""),
        "talent_fit": analysis.get("talent_fit", ""),
        "cover_letter_direction": analysis.get("cover_letter_direction", ""),
        "cover_letter_draft": analysis.get("cover_letter_draft", ""),
        "interview_questions": analysis.get("interview_questions", ""),
        "answer_direction": analysis.get("answer_direction", ""),
        "profile_gap": analysis.get("profile_gap", ""),
        "career_strategy": analysis.get("career_strategy", ""),
        "ai_analysis": analysis.get("ai_analysis", ""),
    }


def collect_from_naver(
    keywords: List[str],
    display: int = 20,
    ai_limit: int = 20,
    user_profile=None,
) -> List[Dict[str, str]]:
    records = []
    seen_keys = set()
    seen_fingerprints = []
    cache = read_analysis_cache()
    cache_changed = False

    headers = {
        "X-Naver-Client-Id": Config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": Config.NAVER_CLIENT_SECRET,
    }

    for keyword in keywords:
        keyword = (keyword or "").strip()

        if not keyword:
            continue

        company_profile = get_company_profile(keyword)
        query = build_search_query(keyword)

        response = requests.get(
            "https://openapi.naver.com/v1/search/news.json",
            headers=headers,
            params={
                "query": query,
                "display": min(max(display * 3, 20), 100),
                "sort": "date",
            },
            timeout=10,
        )
        response.raise_for_status()

        for raw in response.json().get("items", []):
            if len([r for r in records if r["keyword"] == keyword]) >= display:
                break

            title = strip_html(raw.get("title", ""))
            summary = strip_html(raw.get("description", ""))
            link = raw.get("originallink") or raw.get("link", "")
            published = raw.get("pubDate", "")
            cache_key = make_cache_key(link, title, keyword, user_profile)

            if cache_key in seen_keys:
                continue

            if not is_relevant_news(keyword, title, summary):
                continue

            if is_similar_to_existing(title, summary, seen_fingerprints):
                continue

            seen_keys.add(cache_key)
            records.append(
                {
                    "keyword": keyword,
                    "company_profile": company_profile,
                    "cache_key": cache_key,
                    "title": title,
                    "summary": summary,
                    "link": link,
                    "published": published,
                }
            )

    analyze_targets = []

    for index, record in enumerate(records):
        cache_key = record["cache_key"]
        cached = cache.get(cache_key)

        if cached and not is_failed_analysis(cached):
            record["analysis"] = cached
            continue

        if index >= ai_limit:
            record["analysis"] = empty_analysis("AI 호출 제한으로 기본 정보만 표시됩니다.", "skipped")
            continue

        analyze_targets.append(record)

    batch_size = 2

    for start in range(0, len(analyze_targets), batch_size):
        batch = analyze_targets[start:start + batch_size]
        articles = [
            {
                "index": index,
                "title": record["title"],
                "summary": record["summary"],
            }
            for index, record in enumerate(batch)
        ]

        company_profile = batch[0]["company_profile"] if batch else None
        results = analyze_news_batch(
            articles,
            company_profile=company_profile,
            user_profile=user_profile,
        )

        for record, analysis in zip(batch, results):
            if "analysis_status" not in analysis:
                analysis["analysis_status"] = "ok"

            record["analysis"] = analysis

            if not is_failed_analysis(analysis):
                cache[record["cache_key"]] = analysis
                cache_changed = True

    items = []

    for record in records:
        analysis = record.get("analysis", empty_analysis("AI 분석 없음", "failed"))
        item = build_item(
            keyword=record["keyword"],
            company_name=record["company_profile"].get("name", record["keyword"]),
            title=record["title"],
            summary=record["summary"],
            link=record["link"],
            source="naver",
            publisher="네이버 뉴스",
            published=record["published"],
            analysis=analysis,
        )
        items.append(item)

    if cache_changed:
        save_analysis_cache(cache)

    return items


def collect_news(keywords, display=20, ai_limit=20, user_profile=None):
    return collect_from_naver(
        keywords,
        display=display,
        ai_limit=ai_limit,
        user_profile=user_profile,
    )


def save_items(items, keywords_used=None, user_profile=None):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "updated_at": datetime.now().isoformat(),
        "keywords": keywords_used or [],
        "user_profile": user_profile or {},
        "items": items,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def run_collection():
    keywords = ["현대차", "기아", "전기차"]
    items = collect_news(keywords, display=5)
    save_items(items, keywords)
    print(f"수집 완료: {len(items)}건")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keywords", nargs="+", default=None)
    args = parser.parse_args()

    keywords = args.keywords or ["현대차", "기아", "전기차"]
    items = collect_news(keywords, display=5)
    save_items(items, keywords)
    print(f"수집 완료: {len(items)}건")


if __name__ == "__main__":
    main()
