# app/services/web_crawler.py
import asyncio
import re
import urllib.robotparser
import aiohttp
from bs4 import BeautifulSoup, Comment
from urllib.parse import urljoin
from app.utils.logger import logger
from app.utils.cache import cache
import random

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15'
]

CONTENT_TAGS = ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'article', 'section', 'span', 'li', 'td', 'th']

async def check_robots_txt(url: str, session: aiohttp.ClientSession) -> bool:
    try:
        robots_url = urljoin(url, "/robots.txt")
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        async with session.get(robots_url, timeout=10, headers=headers) as response:
            if response.status == 200:
                content = await response.text()
                rp.parse(content.splitlines())
                return rp.can_fetch(headers['User-Agent'], url)
            logger.info(f"Không tìm thấy robots.txt: {robots_url}")
            return True
    except Exception as e:
        logger.error(f"Lỗi khi kiểm tra robots.txt cho {url}: {e}")
        return True  # Bỏ qua nếu không kiểm tra được

async def clean_html_content(html_content: str, query: str) -> str:
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for element in soup(['script', 'style', 'nav', 'footer', '[class*="ad" i]', '[id*="ad" i]', '[class*="sponsor" i]', '[id*="sponsor" i]']) + soup.find_all(string=lambda text: isinstance(text, Comment)):
            element.extract()

        content = []
        query_keywords = set(re.split(r'\s+', query.lower().strip()))
        for tag in soup.find_all(CONTENT_TAGS):
            text = tag.get_text(strip=True)
            if text and len(text) > 50:  # Tăng ngưỡng để lấy nội dung chất lượng
                keyword_matches = sum(1 for keyword in query_keywords if keyword in text.lower())
                if keyword_matches >= len(query_keywords) // 2:  # Yêu cầu khớp ít nhất nửa từ khóa
                    content.append(text)

        title = soup.title.get_text(strip=True) if soup.title else ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        meta_content = meta_desc['content'] if meta_desc and 'content' in meta_desc.attrs else ""

        full_content = f"{title}\n{meta_content}\n" + "\n".join(content)
        full_content = re.sub(r'\s+', ' ', full_content).strip()
        return full_content[:2500]  # Tăng giới hạn để lấy thêm nội dung
    except Exception as e:
        logger.error(f"Lỗi khi làm sạch HTML: {e}")
        return ""

async def crawl_single_url(url: str, session: aiohttp.ClientSession, query: str, retries: int = 3) -> str:
    if url in cache:
        logger.info(f"Lấy nội dung từ cache: {url}")
        return cache[url]

    for attempt in range(retries):
        try:
            if not await check_robots_txt(url, session):
                logger.warning(f"Bị chặn bởi robots.txt: {url}")
                return ""
            headers = {'User-Agent': random.choice(USER_AGENTS)}
            async with session.get(url, timeout=45, headers=headers) as response:
                if response.status in [403, 401, 400]:
                    logger.warning(f"Không thể crawl {url}: Status {response.status}")
                    return ""
                if 'text/html' not in response.headers.get('content-type', '').lower():
                    logger.warning(f"Không phải HTML: {url}")
                    return ""
                html_content = await response.text()
                cleaned_content = await clean_html_content(html_content, query)
                if len(cleaned_content) > 100:  # Chỉ cache nội dung chất lượng
                    cache[url] = cleaned_content
                    logger.info(f"Crawl thành công: {url} - Độ dài: {len(cleaned_content)}")
                    return cleaned_content
                return ""
        except aiohttp.ClientSSLError as ssl_err:
            logger.error(f"Lỗi SSL khi crawl {url}: {ssl_err}")
            return ""
        except aiohttp.ClientError as e:
            logger.error(f"Lỗi khi crawl {url} (thử {attempt + 1}/{retries}): {e}")
            if attempt == retries - 1:
                return ""
            await asyncio.sleep(2)  # Chờ lâu hơn trước khi thử lại
        except Exception as e:
            logger.error(f"Lỗi không xác định khi crawl {url}: {e}")
            return ""
    return ""