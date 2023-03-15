import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures.thread import ThreadPoolExecutor


def scrape_news():
    """
    yahooのサイトからニュースを取得
    """
    
    def get_title_and_url(elem):
        title = elem.find(class_='newsFeed_item_title').text
        res_breaf = requests.get(elem.get('href'))
        html_breaf = BeautifulSoup(res_breaf.content, 'html.parser')
        article_url = html_breaf.select_one('#uamods-pickup > div > div > p > a:nth-child(1)').get('href')
        return (title,article_url)

    res = requests.get('https://news.yahoo.co.jp/topics/top-picks')
    html = BeautifulSoup(res.content, 'html.parser')

    title_url_pair = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        features = [executor.submit(get_title_and_url,elem) for elem in html.select('#contentsWrap > div > div.newsFeed > ul > li > a')]
        for feature in features:
            title_url_pair.append(feature.result())

    return title_url_pair


def scrape_weather(area:str='4410'):
    """
    yahooのサイトから天気を取得
    Args:
        area (str): 地域を表すパラメータ
    """

    res = requests.get(f'https://weather.yahoo.co.jp/weather/jp/13/{area}.html')
    html = BeautifulSoup(res.text, 'html.parser')
    rs = html.find(class_='forecastCity')
    rs = [i.strip() for i in rs.text.splitlines()]
    rs = [i for i in rs if i != ""]
    return rs
