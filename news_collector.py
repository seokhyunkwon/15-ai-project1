import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
import requests
from bs4 import BeautifulSoup

from config import Config


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_FILE = DATA_DIR / "news.json"

# THN은 제외
TARGET_COMPANIES = [
    "서연이화",
    "화신",
    "세원정공",
    "성우하이텍",
    "대원강업",
]

EXCLUDED_COMPANY = "THN"
REGION_KEYWORDS = ["경상", "부산", "울산", "대구", "경남", "경북"]


def _contains_region_keyword(text: str) -> bool:
    return any(keyword in text for keyword in REGION_KEYWORDS)


def _build_item(
    company: str, title: str, link: str, source: str, published: str = ""
) -> Dict[str, str]:
    return {
        "company": company,
        "title": title.strip(),
        "link": link.strip(),
        "source": source,
        "published": published,
    }


def collect_from_naver(companies: List[str]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    if not Config.NAVER_CLIENT_ID or not Config.NAVER_CLIENT_SECRET:
        return items

    headers = {
        "X-Naver-Client-Id": Config.NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": Config.NAVER_CLIENT_SECRET,
    }
    endpoint = "https://openapi.naver.com/v1/search/news.json"

    for company in companies:
        query = f"{company} 현대자동차 협력사"
        params = {"query": query, "display": 10, "sort": "date"}
        response = requests.get(endpoint, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        for raw in data.get("items", []):
            title_html = raw.get("title", "")
            title = BeautifulSoup(title_html, "html.parser").get_text(" ", strip=True)
            desc_html = raw.get("description", "")
            desc = BeautifulSoup(desc_html, "html.parser").get_text(" ", strip=True)
            text_blob = f"{title} {desc}"

            if EXCLUDED_COMPANY.lower() in text_blob.lower():
                continue
            if not _contains_region_keyword(text_blob):
                continue

            items.append(
                _build_item(
                    company=company,
                    title=title,
                    link=raw.get("link", ""),
                    source="naver",
                    published=raw.get("pubDate", ""),
                )
            )
    return items


def collect_from_google(companies: List[str]) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    if not Config.GOOGLE_API_KEY or not Config.GOOGLE_CSE_ID:
        return items

    endpoint = "https://www.googleapis.com/customsearch/v1"
    for company in companies:
        query = f"{company} 현대자동차 협력사 경상권"
        params = {
            "key": Config.GOOGLE_API_KEY,
            "cx": Config.GOOGLE_CSE_ID,
            "q": query,
            "num": 10,
        }
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        for raw in data.get("items", []):
            title = raw.get("title", "")
            snippet = raw.get("snippet", "")
            text_blob = f"{title} {snippet}"

            if EXCLUDED_COMPANY.lower() in text_blob.lower():
                continue
            if not _contains_region_keyword(text_blob):
                continue

            items.append(
                _build_item(
                    company=company,
                    title=title,
                    link=raw.get("link", ""),
                    source="google",
                    published="",
                )
            )
    return items


def deduplicate_items(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    if not items:
        return items
    df = pd.DataFrame(items)
    df = df.drop_duplicates(subset=["title", "link"])
    return df.to_dict(orient="records")


def save_items(items: List[Dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "excluded_company": EXCLUDED_COMPANY,
        "items": items,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def run_collection() -> List[Dict[str, str]]:
    companies = [c for c in TARGET_COMPANIES if c != EXCLUDED_COMPANY]
    naver_items = collect_from_naver(companies)
    google_items = collect_from_google(companies)
    all_items = deduplicate_items(naver_items + google_items)
    save_items(all_items)
    return all_items


if __name__ == "__main__":
    collected = run_collection()
    print(f"수집 완료: {len(collected)}건")
