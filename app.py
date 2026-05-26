from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

from config import CATEGORY_RULES, DEFAULT_INDUSTRY_KEYWORDS

SOURCE_LABELS = {"naver": "네이버", "kakao": "카카오"}
from news_collector import (
    collect_news,
    filter_loaded_items,
    load_payload,
    save_items,
)


def create_app() -> Flask:
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    app = Flask(__name__)
    app.secret_key = "dev-news-dashboard"

    @app.route("/", methods=["GET"])
    def index():
        payload = load_payload()
        search_q = request.args.get("q", "").strip()
        category = request.args.get("category", "전체")
        keyword = request.args.get("keyword", "").strip()
        region_only = request.args.get("region_only") == "1"

        news_items = filter_loaded_items(
            payload,
            keyword_filter=keyword,
            category_filter=category,
            search_query=search_q,
            region_only=region_only,
        )

        categories = payload.get(
            "categories", ["전체"] + list(CATEGORY_RULES.keys()) + ["기타"]
        )
        used_keywords = payload.get("keywords", DEFAULT_INDUSTRY_KEYWORDS)

        return render_template(
            "index.html",
            news_items=news_items,
            updated_at=payload.get("updated_at", ""),
            categories=categories,
            used_keywords=used_keywords,
            default_keywords=", ".join(DEFAULT_INDUSTRY_KEYWORDS),
            search_q=search_q,
            selected_category=category,
            selected_keyword=keyword,
            region_only=region_only,
            api_status=_api_status(),
            source_labels=SOURCE_LABELS,
        )

    @app.route("/collect", methods=["POST"])
    def collect():
        raw = request.form.get("keywords", "").strip()
        include_companies = request.form.get("include_companies") == "on"
        region_only = request.form.get("region_only") == "on"

        if raw:
            keywords = [k.strip() for k in raw.replace("\n", ",").split(",") if k.strip()]
        else:
            keywords = DEFAULT_INDUSTRY_KEYWORDS

        try:
            items = collect_news(
                keywords,
                include_companies=include_companies,
                region_only=region_only,
            )
            save_items(items, keywords)
            flash(f"뉴스 {len(items)}건을 수집했습니다.", "success")
        except Exception as exc:
            flash(f"수집 실패: {exc}", "error")

        return redirect(url_for("index"))

    return app


def _api_status() -> dict:
    load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
    from importlib import reload

    import config as config_module

    reload(config_module)
    cfg = config_module.Config

    return {
        "naver": bool(cfg.NAVER_CLIENT_ID and cfg.NAVER_CLIENT_SECRET),
        "kakao": bool(cfg.KAKAO_REST_API_KEY),
    }


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
