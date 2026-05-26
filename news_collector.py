import argparse
import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import CATEGORY_RULES, Config, DEFAULT_INDUSTRY_KEYWORDS


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news.json"

EXCLUDED_COMPANY = "THN"
REGION_KEYWORDS = ["경상", "부산", "울산", "대구", "경남", "경북"]

# 현대 1차 협력사 (기존 목록 유지)
TARGET_COMPANIES = [
    "서연이화",
    "화신",
    "세원정공",
    "성우하이텍",
    "대원강업",
    "에스엘",
]


def _strip_html(text: str) -> str:
    return BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)


def _parse_published(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        pass
    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value[:10], fmt)
        except ValueError:
            continue
    if value.isdigit() and len(value) >= 8:
        try:
            return datetime.strptime(value[:14].ljust(14, "0"), "%Y%m%d%H%M%S")
        except ValueError:
            pass
    return None


def _publisher_from_url(url: str) -> str:
    host = urlparse(url).netloc or ""
    return host.removeprefix("www.") if host else ""


def _outlet_from_link(link: str) -> str:
    host = _publisher_from_url(link)
    if not host:
        return ""
    if "naver.com" in host:
        return "news.naver.com"
    return host


def classify_category(text: str, search_keyword: str = "") -> str:
    blob = f"{text} {search_keyword}".lower()
    for category, tokens in CATEGORY_RULES.items():
        if any(token.lower() in blob for token in tokens):
            return category
    for category in CATEGORY_RULES:
        if category.replace(" ", "") in search_keyword.replace(" ", ""):
            return category
    return "기타"


def _build_item(
    *,
    keyword: str,
    title: str,
    summary: str,
    link: str,
    source: str,
    publisher: str,
    published: str,
    category: str,
    outlet: str = "",
) -> Dict[str, str]:
    item = {
        "keyword": keyword,
        "category": category,
        "title": title.strip(),
        "summary": summary.strip(),
        "source": source,
        "publisher": publisher,
        "published": published,
        "link": link.strip(),
    }
    if outlet:
        item["outlet"] = outlet
    return item


def collect_from_naver(keywords: List[str], display: int = 10) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    if not Config.NAVER_CLIENT_ID or not Config.NAVER_CLIENT_SECRET:
        return items

    headers = {
        "X-Naver-Client-Id": Config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": Config.NAVER_CLIENT_SECRET,
    }
    endpoint = "https://openapi.naver.com/v1/search/news.json"

    for keyword in keywords:
        params = {"query": keyword, "display": display, "sort": "date"}
        try:
            response = requests.get(endpoint, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            print(f"[naver] '{keyword}' 수집 실패: {exc}")
            continue

        for raw in data.get("items", []):
            title = _strip_html(raw.get("title", ""))
            summary = _strip_html(raw.get("description", ""))
            text_blob = f"{title} {summary}"

            if EXCLUDED_COMPANY.lower() in text_blob.lower():
                continue

            link = raw.get("link", "")
            original_link = raw.get("originallink", "") or link
            outlet = _outlet_from_link(original_link) or _outlet_from_link(link)

            items.append(
                _build_item(
                    keyword=keyword,
                    title=title,
                    summary=summary,
                    link=link,
                    source="naver",
                    publisher="네이버",
                    outlet=outlet,
                    published=raw.get("pubDate", ""),
                    category=classify_category(text_blob, keyword),
                )
            )
    return items


def collect_from_kakao(keywords: List[str], size: int = 10) -> List[Dict[str, str]]:
    """카카오 Daum 웹 검색 API (뉴스 전용 엔드포인트 없음 → 웹 검색 + 최신순)."""
    items: List[Dict[str, str]] = []
    if not Config.KAKAO_REST_API_KEY:
        return items

    headers = {"Authorization": f"KakaoAK {Config.KAKAO_REST_API_KEY}"}
    endpoint = "https://dapi.kakao.com/v2/search/web.json"

    for keyword in keywords:
        params = {"query": keyword, "sort": "recency", "size": min(size, 50)}
        try:
            response = requests.get(
                endpoint, headers=headers, params=params, timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            print(f"[kakao] '{keyword}' 수집 실패: {exc}")
            continue

        for raw in data.get("documents", []):
            title = _strip_html(raw.get("title", ""))
            summary = _strip_html(raw.get("contents", ""))
            link = raw.get("url", "")
            text_blob = f"{title} {summary}"

            if EXCLUDED_COMPANY.lower() in text_blob.lower():
                continue

            dt_raw = raw.get("datetime", "")
            published = ""
            if dt_raw:
                parsed = _parse_published(str(dt_raw))
                published = parsed.strftime("%a, %d %b %Y %H:%M:%S +0900") if parsed else str(dt_raw)

            outlet = _publisher_from_url(link)

            items.append(
                _build_item(
                    keyword=keyword,
                    title=title,
                    summary=summary,
                    link=link,
                    source="kakao",
                    publisher="카카오",
                    outlet=outlet,
                    published=published,
                    category=classify_category(text_blob, keyword),
                )
            )
    return items


def process_dataframe(
    items: List[Dict[str, str]],
    *,
    keyword_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    search_query: Optional[str] = None,
    region_only: bool = False,
) -> pd.DataFrame:
    if not items:
        return pd.DataFrame(
            columns=[
                "keyword",
                "category",
                "title",
                "summary",
                "source",
                "publisher",
                "published",
                "published_dt",
                "link",
            ]
        )

    df = pd.DataFrame(items)
    df["published_dt"] = df["published"].apply(
        lambda v: _parse_published(v) if isinstance(v, str) else None
    )

    if keyword_filter:
        df = df[df["keyword"].str.contains(keyword_filter, case=False, na=False)]

    if category_filter and category_filter != "전체":
        df = df[df["category"] == category_filter]

    if search_query:
        pattern = re.escape(search_query)
        mask = (
            df["title"].str.contains(pattern, case=False, na=False)
            | df["summary"].str.contains(pattern, case=False, na=False)
            | df["keyword"].str.contains(pattern, case=False, na=False)
        )
        df = df[mask]

    if region_only:
        region_mask = df.apply(
            lambda row: any(
                kw in f"{row['title']} {row['summary']}"
                for kw in REGION_KEYWORDS
            ),
            axis=1,
        )
        df = df[region_mask]

    df = df.drop_duplicates(subset=["title", "link"], keep="first")
    df = df.sort_values(
        by="published_dt",
        ascending=False,
        na_position="last",
    )
    return df.reset_index(drop=True)


def dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, str]]:
    if df.empty:
        return []
    out = df.copy()
    out["published_dt"] = out["published_dt"].apply(
        lambda dt: dt.isoformat(timespec="seconds") if pd.notna(dt) else ""
    )
    if "outlet" in out.columns:
        out["outlet"] = out["outlet"].fillna("").astype(str)
        out.loc[out["outlet"].str.lower() == "nan", "outlet"] = ""
    records = out.drop(columns=["published_dt"], errors="ignore").to_dict(orient="records")
    return [
        {k: v for k, v in row.items() if k != "outlet" or (v and str(v).lower() != "nan")}
        for row in records
    ]


def collect_news(
    keywords: List[str],
    *,
    include_companies: bool = False,
    region_only: bool = False,
    display: int = 10,
) -> List[Dict[str, str]]:
    search_terms = [k.strip() for k in keywords if k.strip()]
    if include_companies:
        search_terms.extend(
            c for c in TARGET_COMPANIES if c not in search_terms and c != EXCLUDED_COMPANY
        )

    naver_items = collect_from_naver(search_terms, display=display)
    kakao_items = collect_from_kakao(search_terms, size=display)
    merged = naver_items + kakao_items

    df = process_dataframe(merged, region_only=region_only)
    return dataframe_to_records(df)


def save_items(items: List[Dict[str, str]], keywords_used: List[str]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "keywords": keywords_used,
        "excluded_company": EXCLUDED_COMPANY,
        "categories": ["전체"] + list(CATEGORY_RULES.keys()) + ["기타"],
        "items": items,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def load_payload() -> Dict:
    if not OUTPUT_FILE.exists():
        return {
            "updated_at": "",
            "keywords": [],
            "categories": ["전체"] + list(CATEGORY_RULES.keys()) + ["기타"],
            "items": [],
        }
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def run_collection(
    keywords: Optional[List[str]] = None,
    *,
    include_companies: bool = False,
    region_only: bool = False,
) -> List[Dict[str, str]]:
    kw = keywords or DEFAULT_INDUSTRY_KEYWORDS
    items = collect_news(kw, include_companies=include_companies, region_only=region_only)
    save_items(items, kw)
    return items


def filter_loaded_items(
    payload: Dict,
    *,
    keyword_filter: str = "",
    category_filter: str = "전체",
    search_query: str = "",
    region_only: bool = False,
) -> List[Dict[str, str]]:
    items = payload.get("items", [])
    df = process_dataframe(
        items,
        keyword_filter=keyword_filter or None,
        category_filter=category_filter,
        search_query=search_query or None,
        region_only=region_only,
    )
    return dataframe_to_records(df)


def main() -> None:
    parser = argparse.ArgumentParser(description="산업 키워드 뉴스 수집")
    parser.add_argument(
        "--keywords",
        nargs="+",
        default=None,
        help='검색 키워드 (예: "에스엘" "전기차")',
    )
    parser.add_argument(
        "--companies",
        action="store_true",
        help="1차 협력사 목록도 함께 검색",
    )
    parser.add_argument(
        "--region-only",
        action="store_true",
        help="경상권 키워드가 포함된 기사만 유지",
    )
    args = parser.parse_args()

    keywords = args.keywords or DEFAULT_INDUSTRY_KEYWORDS
    items = run_collection(
        keywords,
        include_companies=args.companies,
        region_only=args.region_only,
    )
    print(f"수집 완료: {len(items)}건 (키워드: {', '.join(keywords)})")
    if not Config.NAVER_CLIENT_ID and not Config.KAKAO_REST_API_KEY:
        print("경고: .env에 NAVER 또는 KAKAO REST API 키가 없습니다.")


if __name__ == "__main__":
    main()
