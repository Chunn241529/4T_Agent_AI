# app/services/llm_router.py
import aiohttp
import base64
import json
import gc
from app.utils.logger import logger

OLLAMA_API_URL = "http://localhost:11434/api/chat"

async def should_search_web(prompt: str) -> bool:
    system_prompt = """
        You are an intelligent routing assistant. Your task is to determine if a user's question requires up-to-date information from the internet to be answered accurately.
        Respond with only "YES" or "NO" in uppercase, without any other text or explanation.

        Respond "YES" for questions about:
        - Current events, news, or recent developments (e.g., "who won the football match yesterday?", "what are the latest AI news?")
        - Real-time information (e.g., "what's the weather in Hanoi?")
        - Specific products, companies, or people where recent information is important (e.g., "what is the latest version of Python?", "tell me about the new Google Gemini model")

        Respond "NO" for questions about:
        - General knowledge that is timeless (e.g., "what is the capital of France?")
        - Creative writing tasks (e.g., "write a poem about the sea")
        - Simple conversational phrases (e.g., "hello", "how are you?")
        - Mathematical calculations (e.g., "what is 2+2?")

        If unsure, respond "NO".
    """
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "gemma3:4b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {"num_keep": 0, "num_predict": 20}
            }
            async with session.post(OLLAMA_API_URL, json=payload) as response:
                if response.status != 200:
                    logger.error(f"Lỗi API Ollama (should_search_web): {response.status}")
                    return False
                data = await response.json()
                decision = data['message']['content'].strip().upper()
                logger.info(f"Quyết định tìm kiếm web: {decision}")
                gc.collect()
                return decision == "YES"
    except Exception as e:
        logger.error(f"Lỗi khi xác định tìm kiếm web: {e}")
        return False

async def generate_search_query(prompt: str) -> str:
    system_prompt = """
        You are an expert at rephrasing user questions into concise, effective English search queries optimized for news and company-related topics.
        Add specific keywords like "2025", "Vietnam", or the company/project name (e.g., "RAGASA") to prioritize reliable sources (e.g., VnExpress, Reuters).
        Avoid ambiguous terms that could match unrelated topics (e.g., "Typhoon Ragasa").
        Output only the search query itself, nothing else.
    """
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "gemma3:4b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"User question: {prompt}"}
                ],
                "stream": False,
                "options": {"num_keep": 0, "num_predict": 100}
            }
            async with session.post(OLLAMA_API_URL, json=payload) as response:
                if response.status != 200:
                    logger.error(f"Lỗi API Ollama (generate_search_query): {response.status}")
                    return f"RAGASA Vietnam 2025 {prompt}"  # Fallback query
                data = await response.json()
                query = data['message']['content'].strip()
                # Đảm bảo query cụ thể hơn
                if "RAGASA" in prompt.upper() and not any(kw in query.lower() for kw in ["typhoon", "storm"]):
                    query = f"RAGASA Vietnam 2025 {query}"
                logger.info(f"Truy vấn tìm kiếm được tạo: {query}")
                gc.collect()
                return query
    except Exception as e:
        logger.error(f"Lỗi khi tạo truy vấn tìm kiếm: {e}")
        return f"RAGASA Vietnam 2025 {prompt}"  # Fallback query

def decode_base64_image(base64_string: str):
    """Giải mã chuỗi base64 thành bytes"""
    try:
        if base64_string.startswith('data:image'):
            base64_string = base64_string.split(',')[1]
        image_bytes = base64.b64decode(base64_string)
        return image_bytes
    except Exception as e:
        logger.error(f"Lỗi khi giải mã ảnh base64: {e}")
        return None