import requests
from bs4 import BeautifulSoup

def get_news_image(url):

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(
        url,
        headers=headers
    )

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    image = soup.find(
        "meta",
        property="og:image"
    )

    if image:

        return image["content"]

    return "https://picsum.photos/500/300"