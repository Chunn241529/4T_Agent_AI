# app/services/web_searcher.py
import asyncio
import numpy as np
from typing import List, Dict, Literal, Optional

from app.services.search_cache import search_cache
from app.services.web_crawler import crawl_urls
from app.services.session_manager import SessionManager
from app.utils.logger import logger

from ddgs import DDGS
from app.utils.embed import embed_text  # Import hàm chung từ utils.embed

OLLAMA_SUMMARY_MODEL = "4T-S"
OLLAMA_API_URL = "http://localhost:11434/api"

async def summarize_text(text: str, query: str) -> str:
    try:
        session = await SessionManager.get_session()
        prompt = f"Tóm tắt ngắn gọn (<=5 câu) nội dung sau, tập trung vào: {query}\n\n{text}"
        payload = {
            "model": OLLAMA_SUMMARY_MODEL,
            "prompt": prompt,
            "stream": False,
        }
        async with session.post(f"{OLLAMA_API_URL}/generate", json=payload) as resp:
            data = await resp.json()
            return data.get("response", "").strip()
    except Exception as e:
        logger.error(f"Lỗi summarize: {e}")
        return text[:500]

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

async def fallback_search(query: str, max_results: int = 10) -> List[str]:
    try:
        url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127 Safari/537.36"}
        session = await SessionManager.get_session()
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return []
            html = await resp.text()
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")
            links = [a["href"] for a in soup.select("li.b_algo h2 a")[:max_results] if "href" in a.attrs]
            return links
    except Exception as e:
        logger.error(f"Lỗi fallback search: {e}")
        return []

async def search_web(
    query: str,
    max_results: int = 5,
    mode: Literal["raw", "rerank", "summary"] = "rerank",
    rerank_top_k: int = 5,
) -> List[Dict]:
    """
    Search web với 3 chế độ:
      - raw: chỉ lấy kết quả search + crawl
      - rerank: semantic re-rank
      - summary: tóm tắt content
    """
    cached = search_cache.get(query)
    if cached:
        logger.info(f"Dùng cache cho query: {query}")
        return cached

    results = []
    try:
        urls = []
        try:
            ddgs = DDGS()
            search_hits = ddgs.text(query, region="us-en", max_results=max_results)
            urls = [h["href"] for h in search_hits if "href" in h]
        except Exception as e:
            logger.error(f"Lỗi DDGS: {e}, dùng fallback Bing")
            urls = await fallback_search(query, max_results)

        if not urls:
            return []

        crawled = await crawl_urls(urls, query=query, concurrency=10)

        if mode == "raw":
            results = crawled

        elif mode == "rerank":
            qvec = await embed_text(query)
            if qvec is None:
                results = crawled
            else:
                scored = []
                for item in crawled:
                    vec = await embed_text(item["title"] + " " + item["content"][:500])
                    if vec is not None:
                        score = cosine_similarity(qvec, vec)
                        scored.append((score, item))
                scored.sort(key=lambda x: x[0], reverse=True)
                results = [it for _, it in scored[:rerank_top_k]]

        elif mode == "summary":
            tasks = [summarize_text(item["content"], query) for item in crawled]
            summaries = await asyncio.gather(*tasks, return_exceptions=True)
            for item, summ in zip(crawled, summaries):
                if isinstance(summ, str) and summ.strip():
                    results.append({
                        "url": item["url"],
                        "title": item["title"],
                        "summary": summ
                    })

        if results:
            search_cache.set(query, results)

        return results

    except Exception as e:
        logger.error(f"Lỗi search_web({mode}): {e}")
        return []
