# app/services/web_crawler.py
import asyncio
import aiohttp
import aiohttp.http_parser as http_parser
import random
import re
from typing import List, Dict, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from urllib.robotparser import RobotFileParser

from app.utils.logger import logger
from app.utils.cache import cache

http_parser.DEF_MAX_LINE_SIZE = 32768
http_parser.DEF_MAX_FIELD_SIZE = 32768

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.6; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (compatible; Baiduspider/2.0; +http://www.baidu.com/search/spider.html)",
    "Mozilla/5.0 (compatible; Sogou web spider/4.0; +http://www.sogou.com/docs/help/webmasters.htm#07)",
]

TRUSTED_DOMAINS = [
    "vnexpress.net", "thanhnien.vn", "tuoitre.vn", "nld.com.vn",
    "bbc.com", "cnn.com", "reuters.com", "apnews.com",
    "nytimes.com", "theguardian.com", "aljazeera.com",
    "wikipedia.org", "arxiv.org", "springer.com", "nature.com",
    "github.com", "huggingface.co", "gitlab.com",
    "stackoverflow.com", "pypi.org", "npmjs.com", "pkg.go.dev",
    "crates.io", "rubygems.org", "dockerhub.com",
    "readthedocs.io", "medium.com", "towardsdatascience.com", "dev.to"
]

def clean_html_content(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "header", "footer", "form", "iframe"]):
        tag.extract()
    main_content = soup.find("article") or soup.find("main") or soup.find("body")
    if main_content:
        text = main_content.get_text(separator="\n")
    else:
        text = soup.get_text(separator="\n")
    text = re.sub(r"\n\s*\n", "\n", text)
    return text.strip()

async def check_robots_txt(url: str, session: aiohttp.ClientSession, user_agent: str) -> bool:
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        async with session.get(robots_url, timeout=5) as resp:
            if resp.status != 200:
                return True
            text = await resp.text()
            rp = RobotFileParser()
            rp.parse(text.splitlines())
            return rp.can_fetch(user_agent, url)
    except Exception:
        return True

async def crawl_single_url(
    url: str,
    session: aiohttp.ClientSession,
    query: str = "",
    retries: int = 5,
    timeout: int = 30,
) -> Optional[str]:
    cache_key = f"url::{url}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    for attempt in range(retries):
        user_agent = random.choice(USER_AGENTS)
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": random.choice(["en-US,en;q=0.9", "zh-CN,zh;q=0.9,en;q=0.8", "id-ID,id;q=0.9,en;q=0.8"]),
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Referer": random.choice(["https://www.google.com/", "https://www.bing.com/", "https://www.baidu.com/"]),
            "DNT": "1",
        }

        try:
            allowed = await check_robots_txt(url, session, user_agent)
            if not allowed:
                logger.info(f"Robots.txt chặn: {url}")
                return None

            await asyncio.sleep(random.uniform(1.0, 3.0))

            async with session.get(url, headers=headers, timeout=timeout) as resp:
                if resp.status in [401, 403, 429]:
                    logger.warning(f"Blocked {url} - status {resp.status}")
                    await asyncio.sleep(1.5 ** attempt + random.uniform(0, 1))
                    continue
                if resp.status != 200:
                    logger.warning(f"Lỗi {url}: HTTP {resp.status}")
                    continue

                html = await resp.text(errors="ignore")
                text = clean_html_content(html)
                if not text or len(text) < 200:
                    continue

                cache[cache_key] = text
                return text

        except Exception as e:
            logger.error(f"Lỗi crawl {url}: {e}")
            await asyncio.sleep(1.5 ** attempt + random.uniform(0, 1))

    return None

async def crawl_urls(
    urls: List[str],
    query: str = "",
    concurrency: int = 10,
    timeout: int = 30,
) -> List[Dict[str, str]]:
    if not urls:
        return []

    results: List[Dict[str, str]] = []
    semaphore = asyncio.Semaphore(concurrency)

    conn = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=conn) as session:

        async def _crawl_one(u: str) -> Optional[Dict[str, str]]:
            async with semaphore:
                try:
                    if not u:
                        return None
                    content = await crawl_single_url(u, session, query, retries=5, timeout=timeout)
                    if not content or len(content) < 100:
                        return None
                    title = content.split("\n")[0].strip() if "\n" in content else content[:120].strip()
                    if not title:
                        title = u
                    return {"url": u, "title": title, "content": content}
                except Exception as e:
                    logger.error(f"Lỗi khi crawl url {u}: {e}")
                    return None

        tasks = [_crawl_one(u) for u in urls]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

    for item in completed:
        if isinstance(item, dict):
            results.append(item)

    return results
