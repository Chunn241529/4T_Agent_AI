# app/services/web_searcher.py
import asyncio
from ddgs import DDGS
from app.utils.logger import logger
from app.services.web_crawler import crawl_single_url
import aiohttp

TRUSTED_DOMAINS = [
    'vnexpress.net', 'reuters.com', 'bbc.com', 'theguardian.com',
    'nytimes.com', 'washingtonpost.com', 'lego.com', 'apnews.com'
]

def sync_search_ddg(query: str):
    try:
        logger.info(f"Đang tìm kiếm DuckDuckGo: {query}")
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=10)  # Tăng để có thêm lựa chọn
            urls = [
                result['href'] for result in results
                if result['href'].startswith('http') and
                'login' not in result['href'].lower() and
                not any(kw in result['href'].lower() for kw in ['typhoon', 'storm'])
            ]
            # Ưu tiên domain đáng tin cậy
            trusted_urls = [url for url in urls if any(domain in url.lower() for domain in TRUSTED_DOMAINS)]
            other_urls = [url for url in urls if url not in trusted_urls]
            logger.info(f"Tìm thấy {len(urls)} URL từ DuckDuckGo (trusted: {len(trusted_urls)})")
            return trusted_urls + other_urls[:10 - len(trusted_urls)]  # Giới hạn 10 URL
    except Exception as e:
        logger.error(f"Lỗi khi tìm kiếm DuckDuckGo: {e}")
        return []

async def search_web(query: str):
    try:
        urls = await asyncio.to_thread(sync_search_ddg, query)
        if not urls:
            logger.info("Không tìm thấy URL nào từ DuckDuckGo")
            return [{"url": "", "content": "Không tìm thấy thông tin về RAGASA 2025. Vui lòng thử lại với từ khóa cụ thể hơn.", "title": "Không có kết quả"}]

        async with aiohttp.ClientSession() as session:
            tasks = [crawl_single_url(url, session, query) for url in urls]
            contents = await asyncio.gather(*tasks, return_exceptions=True)

            results = []
            for url, content in zip(urls, contents):
                if isinstance(content, str) and content and len(content) > 150:  # Tăng ngưỡng chất lượng
                    title = content.split('\n')[0] or url
                    results.append({"url": url, "content": content, "title": title})

            if not results:
                logger.info("Không crawl được nội dung chất lượng từ các URL")
                return [{"url": "", "content": "Không thể crawl thông tin về RAGASA 2025 do giới hạn truy cập hoặc thiếu nội dung liên quan.", "title": "Không có kết quả"}]

            logger.info(f"Số kết quả crawl được: {len(results)}")
            return results[:3]  # Giới hạn 3 kết quả chất lượng
    except Exception as e:
        logger.error(f"Lỗi khi tìm kiếm web: {e}")
        return [{"url": "", "content": "Lỗi khi tìm kiếm thông tin về RAGASA 2025.", "title": "Lỗi tìm kiếm"}]