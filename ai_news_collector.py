# ================================
# news_collector.py
# ================================

import json
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from config import (
    Config,
    DEFAULT_INDUSTRY_KEYWORDS
)

from ai_analyzer import analyze_news


BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"

OUTPUT_FILE = DATA_DIR / "news.json"


def strip_html(text):

    return BeautifulSoup(
        text or "",
        "html.parser"
    ).get_text(" ", strip=True)


def build_item(
    keyword,
    title,
    summary,
    link,
    published,
    ai_analysis
):

    return {
        "keyword": keyword,
        "title": title,
        "summary": summary,
        "link": link,
        "published": published,
        "ai_analysis": ai_analysis
    }


def collect_news(keywords, display=2):

    items = []

    headers = {
        "X-Naver-Client-Id":
        Config.NAVER_CLIENT_ID,

        "X-Naver-Client-Secret":
        Config.NAVER_CLIENT_SECRET,
    }

    endpoint = (
        "https://openapi.naver.com/v1/search/news.json"
    )

    for keyword in keywords:

        params = {
            "query": keyword,
            "display": display,
            "sort": "date"
        }

        try:

            response = requests.get(
                endpoint,
                headers=headers,
                params=params,
                timeout=10
            )

            response.raise_for_status()

            data = response.json()

        except Exception as e:

            print(f"[뉴스 수집 실패] {e}")

            continue

        for raw in data.get("items", []):

            title = strip_html(
                raw.get("title", "")
            )

            summary = strip_html(
                raw.get("description", "")
            )

            link = raw.get("link", "")

            published = raw.get(
                "pubDate",
                ""
            )

            # =========================
            # AI 분석
            # =========================

            ai_analysis = analyze_news(
                title,
                summary
            )

            item = build_item(
                keyword=keyword,
                title=title,
                summary=summary,
                link=link,
                published=published,
                ai_analysis=ai_analysis
            )

            items.append(item)

    return items


def save_items(items):

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    payload = {
        "updated_at":
        datetime.now().isoformat(),

        "items":
        items
    }

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            payload,
            f,
            ensure_ascii=False,
            indent=2
        )


def run_collection():

    items = collect_news(
        DEFAULT_INDUSTRY_KEYWORDS
    )

    save_items(items)

    print(f"{len(items)}개 저장 완료")


if __name__ == "__main__":

    run_collection()