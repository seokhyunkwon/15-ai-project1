from flask import Flask, render_template
import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "news.json"


def create_app() -> Flask:
    app = Flask(__name__)

    @app.route("/")
    def index():
        news_items = []
        if DATA_FILE.exists():
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                payload = json.load(f)
                news_items = payload.get("items", [])

        return render_template("index.html", news_items=news_items)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
