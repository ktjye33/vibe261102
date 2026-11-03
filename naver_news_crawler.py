"""
네이버 검색 결과에서 뉴스 기사를 찾아 본문까지 크롤링하는 스크립트 (BeautifulSoup4)

설치:
    pip install requests beautifulsoup4

사용:
    python naver_news_crawler.py            # 기본 검색어 '반도체'
    python naver_news_crawler.py 인공지능 20  # 검색어, 최대 기사 수
"""
import csv
import re
import sys
import time
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# 네이버 뉴스(본문을 네이버가 직접 호스팅하는 기사) 주소 패턴
NAVER_ARTICLE_RE = re.compile(r"https://n\.news\.naver\.com/(?:mnews/)?article/\d+/\d+")


def build_search_urls(query):
    """사용자가 준 통합검색(nexearch) URL과, 기사가 더 많이 나오는 뉴스탭 URL."""
    q = quote(query)
    return [
        f"https://search.naver.com/search.naver?where=nexearch&sm=top_hty&fbm=0&ie=utf8&query={q}",
        f"https://search.naver.com/search.naver?where=news&sm=tab_jum&query={q}",
    ]


def get_soup(url):
    res = requests.get(url, headers=HEADERS, timeout=10)
    res.raise_for_status()
    return BeautifulSoup(res.text, "html.parser")


def collect_article_links(query, limit):
    """검색 결과 페이지에서 네이버 뉴스 기사 링크를 중복 없이 수집."""
    links = []
    for url in build_search_urls(query):
        soup = get_soup(url)
        # 네이버 검색 결과의 class 이름은 자주 바뀌므로, href 패턴으로 찾는 것이 안정적이다.
        for a in soup.find_all("a", href=True):
            m = NAVER_ARTICLE_RE.match(a["href"])
            if m and m.group(0) not in links:
                links.append(m.group(0))
                if len(links) >= limit:
                    return links
    return links


def text_of(soup, selector):
    tag = soup.select_one(selector)
    return tag.get_text(" ", strip=True) if tag else ""


def parse_article(url):
    """n.news.naver.com 기사 페이지에서 제목/언론사/날짜/본문 추출."""
    soup = get_soup(url)

    title = text_of(soup, "#title_area") or text_of(soup, "h2.media_end_head_headline")

    press_img = soup.select_one("a.media_end_head_top_logo img")
    press = press_img.get("alt", "") if press_img else ""

    date_tag = soup.select_one("span.media_end_head_info_datestamp_time")
    date = date_tag.get("data-date-time", date_tag.get_text(strip=True)) if date_tag else ""

    body_tag = soup.select_one("#dic_area") or soup.select_one("#newsct_article")
    body = ""
    if body_tag:
        # 사진 설명, 스크립트 등 본문이 아닌 요소 제거
        for junk in body_tag.select("script, style, .img_desc, .end_photo_org em, .media_end_summary"):
            junk.decompose()
        body = body_tag.get_text("\n", strip=True)

    return {"title": title, "press": press, "date": date, "url": url, "body": body}


def save_csv(articles, filename):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:  # 엑셀 한글 깨짐 방지
        writer = csv.DictWriter(f, fieldnames=["title", "press", "date", "url", "body"])
        writer.writeheader()
        writer.writerows(articles)


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else "반도체"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10

    links = collect_article_links(query, limit)
    print(f"[{query}] 기사 링크 {len(links)}개 수집\n")

    articles = []
    for i, link in enumerate(links, 1):
        try:
            article = parse_article(link)
        except requests.RequestException as e:
            print(f"{i}. 실패: {link} ({e})")
            continue
        articles.append(article)
        print(f"{i}. [{article['press']}] {article['title']} ({article['date']})")
        print(f"   {article['url']}")
        print(f"   {article['body'][:150].replace(chr(10), ' ')}...\n")
        time.sleep(0.5)  # 서버 부담을 줄이기 위한 요청 간격

    filename = f"naver_news_{query}.csv"
    save_csv(articles, filename)
    print(f"{len(articles)}개 기사를 {filename} 에 저장했습니다.")


if __name__ == "__main__":
    main()
