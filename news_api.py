from crawler import get_news_image
import requests
import re
import html

client_id = "zcJPKaKkhJpQ4NJpOXgI"
client_secret = "VAit_CLQ_P"


def get_news(keyword):

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

    response = requests.get(
        url,
        headers=headers,
        params=params
    )

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

    return news_list