print("### APP 실행중 ###")

from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, abort, render_template, request

from config import DEFAULT_INDUSTRY_KEYWORDS
from news_collector import (
    TARGET_COMPANIES,
    collect_news,
    generate_llm_analysis,
    load_payload,
    save_items,
)

SOURCE_LABELS = {"naver": "네이버", "kakao": "카카오"}

COMPANY_ALIASES = {
    "THN": ["THN", "티에이치엔"],
    "현대자동차": ["현대자동차", "현대차"],
    "에스엘": ["에스엘", "SL"],
}

def _keywords_from_role(role: str) -> list[str]:
    keywords = [k.strip() for k in role.replace("\n", ",").split(",") if k.strip()]
    return keywords or DEFAULT_INDUSTRY_KEYWORDS


# def _matches_company(item: dict, company_name: str) -> bool:
#     text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
#     return company_name.lower() in text

def _matches_company(item, company_name):

    aliases = COMPANY_ALIASES.get(
        company_name,
        [company_name]
    )

    text = (
        item.get("title", "")
        + " "
        + item.get("summary", "")
    ).lower()

    return any(
        alias.lower() in text
        for alias in aliases
    )

def create_app() -> Flask:
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

    app = Flask(__name__)
    app.secret_key = "automotive-clean-light-blue-intelligence-dashboard"

    @app.route("/", methods=["GET", "POST"])
    def index():
        payload = load_payload()
        news_items = payload.get("items", [])
        role = request.form.get("role", "").strip()
        notice = None

        if request.method == "POST":
            search_keywords = _keywords_from_role(role)
            try:
                fetched_items = collect_news(search_keywords, include_companies=True)
                save_items(fetched_items, search_keywords)
                news_items = fetched_items

                if fetched_items:
                    notice = f"실시간 뉴스 {len(fetched_items)}건을 수집했습니다."
                else:
                    notice = f"입력한 키워드({', '.join(search_keywords)})로 검색된 실제 뉴스가 없습니다."
            except Exception as exc:
                notice = f"뉴스 수집 중 오류가 발생했습니다: {exc}"

        return render_template(
            "index.html",
            target_companies=TARGET_COMPANIES,
            role=role,
            news_items=news_items,
            source_labels=SOURCE_LABELS,
            notice=notice,
        )

    @app.route("/company/<company_name>", methods=["GET"])
    def company_detail(company_name):

        print("=" * 50)
        print("company_detail 진입")
        print("company =", company_name)

        if company_name not in TARGET_COMPANIES:
            abort(404)

        payload = load_payload()

        cached_items = payload.get("items", [])

        print("전체 뉴스 수 =", len(cached_items))

        filtered_news = [
            item for item in cached_items
            if _matches_company(item, company_name)
        ]

        print("필터 뉴스 수 =", len(filtered_news))

        if not filtered_news:
            print("뉴스 재수집 시작")

            filtered_news = collect_news(
                [company_name,
                f"{company_name} 자동차 부품",
                f"{company_name} 전장"],
                include_companies=False,
            )

        company_news_titles = [
            item.get("title", "")
            for item in filtered_news
            if item.get("title")
        ]

        print("뉴스 제목 수 =", len(company_news_titles))

        print("AI 분석 호출 직전")

        analysis = generate_llm_analysis(
            company_name,
            company_news_titles
        )

        print("AI 분석 호출 완료")
        print(analysis)

        return render_template(
            "company_detail.html",
            company_name=company_name,
            analysis=analysis,
            news_items=filtered_news,
            source_labels=SOURCE_LABELS,
        )

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
