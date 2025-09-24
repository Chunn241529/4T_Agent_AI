# app/services/web_searcher.py

import asyncio
from ddgs import DDGS
from app.utils.logger import logger
from app.services.web_crawler import crawl_single_url
import aiohttp

def sync_search_ddg(query: str):
    try:
        logger.info(f"Đang tìm kiếm DuckDuckGo: {query}")
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=5)
            urls = [result['href'] for result in results if result['href'].startswith('http')]
            logger.info(f"Tìm thấy {len(urls)} URL từ DuckDuckGo")
            return urls
    except Exception as e:
        logger.error(f"Lỗi khi tìm kiếm DuckDuckGo: {e}")
        return []

async def search_web(query: str):
    try:
        urls = await asyncio.to_thread(sync_search_ddg, query)
        if not urls:
            return [{"url": "", "content": "Không tìm thấy nội dung web phù hợp.", "title": "Không có kết quả"}]

        async with aiohttp.ClientSession() as session:
            tasks = [crawl_single_url(url, session, query) for url in urls]
            contents = await asyncio.gather(*tasks, return_exceptions=True)

            results = []
            for url, content in zip(urls, contents):
                if isinstance(content, str) and content and len(content) > 50:
                    title = content.split('\n')[0] or url
                    results.append({"url": url, "content": content, "title": title})

            if not results:
                results.append({"url": "", "content": "Không thể crawl nội dung từ các nguồn web do giới hạn robots.txt hoặc lỗi khác.", "title": "Không có kết quả"})

            logger.info(f"Số kết quả crawl được: {len(results)}")
            return results
    except Exception as e:
        logger.error(f"Lỗi khi tìm kiếm web: {e}")
        return [{"url": "", "content": "Lỗi khi tìm kiếm web.", "title": "Lỗi tìm kiếm"}]
