from crawler import get_news_image
import requests
import re
import html
import time

client_id = "zcJPKaKkhJpQ4NJpOXgI"
client_secret = "VAit_CLQ_P"
NEWS_CACHE_SECONDS = 600
_news_cache = {}


def get_news(keyword):
    now = time.time()
    cached = _news_cache.get(keyword)

    if cached and now - cached["time"] < NEWS_CACHE_SECONDS:
        return [item.copy() for item in cached["items"]]

    url = "https://openapi.naver.com/v1/search/news.json"

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }

    params = {
        "query": keyword,
        "display": 5,
        "sort": "date"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=4
        )
        response.raise_for_status()
    except requests.RequestException:
        if cached:
            return [item.copy() for item in cached["items"]]
        return []

    data = response.json()

    news_list = []

    if 'items' in data:

        for item in data['items']:

            image_url = get_news_image(
                item['link']
            )

            title = re.sub(
            '<.*?>',
            '',
            item['title']
            )

            title = html.unescape(title)

            description = re.sub(
                '<.*?>',
                '',
                item['description']
            )

            description = html.unescape(description)

            news_list.append({
                "title": title,
                "description": description,
                "link": item['link'],
                "image": image_url
            })

    _news_cache[keyword] = {
        "time": now,
        "items": [item.copy() for item in news_list]
    }

    return news_list
