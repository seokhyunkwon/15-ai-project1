import requests
from bs4 import BeautifulSoup
from functools import lru_cache

FALLBACK_IMAGE = "https://picsum.photos/500/300"


@lru_cache(maxsize=256)
def get_news_image(url):

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=2
        )
        response.raise_for_status()
    except requests.RequestException:
        return FALLBACK_IMAGE

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    image = soup.find(
        "meta",
        property="og:image"
    )

    if image:

        return image.get("content", FALLBACK_IMAGE)

    return FALLBACK_IMAGE
