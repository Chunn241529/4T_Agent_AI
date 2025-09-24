# app/services/llm_router.py

import ollama
from app.utils.logger import logger

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
        response = await ollama.AsyncClient().chat(
            model="gemma3:4b",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        )
        decision = response['message']['content'].strip().upper()
        logger.info(f"Quyết định tìm kiếm web: {decision}")
        return decision == "YES"
    except Exception as e:
        logger.error(f"Lỗi khi xác định tìm kiếm web: {e}")
        return False

async def generate_search_query(prompt: str) -> str:
    system_prompt = """
        You are an expert at rephrasing user questions into concise, effective English search queries optimized for news and weather-related topics.
        Add relevant keywords like "2025", "Vietnam", or specific terms to prioritize reliable news sources (e.g., VnExpress, AccuWeather).
        Output only the search query itself, nothing else.
    """
    try:
        response = await ollama.AsyncClient().chat(
            model="gemma3:4b",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"User question: {prompt}"}]
        )
        query = response['message']['content'].strip()
        logger.info(f"Truy vấn tìm kiếm được tạo: {query}")
        return query
    except Exception as e:
        logger.error(f"Lỗi khi tạo truy vấn tìm kiếm: {e}")
        return prompt
