# app/services/web_crawler.py

import re
import urllib
import aiohttp
from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin
from app.utils.logger import logger
from app.utils.cache import cache

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

CONTENT_TAGS = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'article', 'section', 'span', 'li', 'td', 'th']

async def check_robots_txt(url: str, session: aiohttp.ClientSession) -> bool:
    try:
        robots_url = urljoin(url, "/robots.txt")
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        async with session.get(robots_url, timeout=5, headers=HEADERS) as response:
            if response.status == 200:
                content = await response.text()
                rp.parse(content.splitlines())
                return rp.can_fetch(HEADERS['User-Agent'], url)
            else:
                logger.info(f"Không tìm thấy robots.txt: {robots_url}")
                return True
        return True
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra robots.txt cho {url}: {e}")
        return True

async def clean_html_content(html_content: str, query: str) -> str:
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'footer', '[class*="ad" i]', '[id*="ad" i]', '[class*="sponsor" i]', '[id*="sponsor" i]']) + soup.find_all(string=lambda text: isinstance(text, Comment)):
            element.extract()

        content = []
        query_keywords = set(query.lower().split())
        for tag in soup.find_all(CONTENT_TAGS):
            text = tag.get_text(strip=True)
            if text and len(text) > 15:
                if any(keyword in text.lower() for keyword in query_keywords):
                    content.append(text)

        title = soup.title.get_text(strip=True) if soup.title else ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_content = meta_desc['content'] if meta_desc and 'content' in meta_desc.attrs else ""

        full_content = f"{title}\n{meta_content}\n" + "\n".join(content)
        full_content = re.sub(r'\s+', ' ', full_content).strip()
        return full_content[:1500]
    except Exception as e:
        logger.error(f"Lỗi khi làm sạch HTML: {e}")
        return ""

async def crawl_single_url(url: str, session: aiohttp.ClientSession, query: str) -> str:
    if url in cache:
        logger.info(f"Lấy nội dung từ cache: {url}")
        return cache[url]

    try:
        if not await check_robots_txt(url, session):
            return ""
        async with session.get(url, timeout=15, headers=HEADERS) as response:
            if response.status != 200 or 'text/html' not in response.headers.get('content-type', ''):
                logger.warning(f"Không thể crawl {url}: Status {response.status}")
                return ""
            html_content = await response.text()
            cleaned_content = await clean_html_content(html_content, query)
            cache[url] = cleaned_content
            logger.info(f"Crawl thành công: {url} - Độ dài: {len(cleaned_content)}")
            return cleaned_content
    except Exception as e:
        logger.error(f"Lỗi khi crawl {url}: {e}")
        return ""
