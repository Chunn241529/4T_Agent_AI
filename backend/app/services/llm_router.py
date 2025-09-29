# app/services/llm_router.py
import re
import base64
import json
from typing import Optional, Set
from app.utils.logger import logger
from app.services.get_time import get_current_time_info
from app.services.session_manager import SessionManager

OLLAMA_API_URL = "http://localhost:11434/api/chat"
model_check = "4T-S"  # Sử dụng model nhỏ hơn cho routing

# Keywords cho quick check trước khi dùng LLM
SEARCH_KEYWORDS = {
    # Từ khóa tìm kiếm cơ bản
    'search', 'tìm', 'tra', 'lookup', 'find',
    'tin tức', 'news', 'mới nhất', 'latest',
    'giá', 'price', 'bao nhiêu', 'how much',
    'hiện tại', 'now', 'current', 'hôm nay', 'today',
    'update', 'cập nhật', 'thời sự', 'thông tin',

    # Từ khóa mới thêm vào
    'thị trường', 'market', 'triển khai', 'deploy',
    'version', 'phiên bản', 'trending', 'xu hướng',
    'stock', 'chứng khoán', 'cryptocurrency', 'crypto',
    'weather', 'thời tiết', 'forecast', 'dự báo'
}

# Thinking trigger keywords
THINKING_TRIGGER_KEYWORDS = {
    # Phân tích và suy luận
    'phân tích', 'suy nghĩ', 'đánh giá', 'xem xét', 'nghiên cứu',
    'tính toán', 'so sánh', 'đề xuất', 'giải thích', 'tối ưu',
    'lập luận', 'chứng minh', 'lí giải', 'phản biện',

    # Từ khóa chỉ định rõ cần suy luận
    'tại sao', 'vì sao', 'như thế nào', 'bằng cách nào',
    'ưu điểm', 'nhược điểm', 'hậu quả', 'nguyên nhân',
    'mối quan hệ', 'ảnh hưởng', 'tác động', 'kết quả',

    # Từ khóa liên quan đến trí tuệ
    'thông minh', 'trí tuệ', 'sáng tạo', 'phát minh',
    'chiến lược', 'kế hoạch', 'giải pháp', 'cải tiến'
}

# Cache cho kết quả search decision
search_decision_cache: dict = {}

def _quick_search_check(prompt: str) -> Optional[bool]:
    """Kiểm tra nhanh dựa trên keywords trước khi dùng LLM"""
    prompt_lower = prompt.lower()

    # Cache check
    if prompt_lower in search_decision_cache:
        return search_decision_cache[prompt_lower]

    # Quick rejection patterns
    if re.match(r'^(hi|hello|hey|chào|xin chào|test)', prompt_lower):
        search_decision_cache[prompt_lower] = False
        return False

    # Kiểm tra thinking keywords trước
    has_thinking_keywords = any(kw in prompt_lower for kw in THINKING_TRIGGER_KEYWORDS)

    # Kiểm tra search keywords
    has_search_keywords = any(kw in prompt_lower for kw in SEARCH_KEYWORDS)

    # Xử lý các trường hợp đặc biệt
    if has_thinking_keywords and not has_search_keywords:
        # Nếu chỉ có thinking keywords, không cần search
        search_decision_cache[prompt_lower] = False
        return False

    if has_search_keywords:
        # Nếu có search keywords, cho phép search
        search_decision_cache[prompt_lower] = True
        return True

    # Các pattern khác cần LLM quyết định
    return None

async def should_search_web(prompt: str) -> bool:
    # Thử quick check trước
    quick_result = _quick_search_check(prompt)
    if quick_result is not None:
        return quick_result

    current_time = get_current_time_info()
    system_prompt = f"""
          {current_time}.
          You are an intelligent routing assistant. Your task is to determine if a user's question requires up-to-date information from the internet to be answered accurately.
          Respond with only "YES" or "NO" in uppercase, without any other text or explanation.

          Respond "YES" for questions about:
          - Current events, news, or recent developments (e.g., "who won the football match yesterday?", "what are the latest AI news?")
          - Real-time external information that cannot be inferred from {current_time} alone (e.g., "what's the weather in Hanoi?", "what is the stock price of Apple right now?")
          - Specific products, companies, or people where recent information is important (e.g., "what is the latest version of Python?", "tell me about the new Google Gemini model")
          - Explicit requests for searching, looking up, or retrieving web information (e.g., "search for the best laptops 2025", "find recent articles on climate change", "browse the latest stock prices")

          Respond "NO" for questions about:
          - General knowledge that is timeless (e.g., "what is the capital of France?")
          - Creative writing tasks (e.g., "write a poem about the sea")
          - Simple conversational phrases (e.g., "hello", "how are you?")
          - Mathematical calculations (e.g., "what is 2+2?")
          - Questions about the current local time or date (e.g., "what time is it now?", "today's date")

          If unsure, lean towards "YES" if the question implies a desire for external search or fresh data; otherwise, "NO".
    """
    try:
        session = await SessionManager.get_session()
        payload = {
            "model": model_check,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False,
            "options": {"num_keep": 0, "num_predict": 20, "temperature": 0.2}
        }
        async with session.post(OLLAMA_API_URL, json=payload) as response:
            if response.status != 200:
                logger.error(f"Lỗi API Ollama (should_search_web): {response.status}")
                return False
            data = await response.json()
            decision = data['message']['content'].strip().upper()
            logger.info(f"Quyết định tìm kiếm web: {decision}")
            # Cache kết quả
            search_decision_cache[prompt.lower()] = (decision == "YES")
            return decision == "YES"
    except Exception as e:
        logger.error(f"Lỗi khi xác định tìm kiếm web: {e}")
        return False

async def should_thinking(messages_for_llm: list) -> bool:
    """
    Quyết định xem có nên dùng chế độ suy luận dựa trên context và prompt.
    """
    # Lấy prompt từ tin nhắn cuối cùng của user
    user_msg = next((msg for msg in reversed(messages_for_llm) if msg["role"] == "user"), None)
    if not user_msg:
        return False

    prompt = user_msg["content"].lower()
    word_count = len(prompt.split())

    # Kiểm tra từ khóa suy luận
    has_thinking_keywords = any(kw in prompt for kw in THINKING_TRIGGER_KEYWORDS)

    # Kiểm tra từ khóa tìm kiếm
    has_search_keywords = any(kw in prompt for kw in SEARCH_KEYWORDS)

    # Các trường hợp đặc biệt
    special_cases = [
        "web_context" in prompt,
        "phân tích ảnh" in prompt,
        word_count > 50  # Câu hỏi dài
    ]

    # Logic quyết định:
    if has_thinking_keywords:
        # Nếu có thinking keywords, luôn bật suy luận
        logger.info(f"Kích hoạt suy luận do từ khóa thinking")
        return True

    if any(special_cases):
        # Các trường hợp đặc biệt cần suy luận
        logger.info(f"Kích hoạt suy luận do trường hợp đặc biệt")
        return True

    if has_search_keywords and word_count > 30:
        # Câu search phức tạp cần suy luận
        logger.info(f"Kích hoạt suy luận do search phức tạp")
        return True

    return False

async def generate_search_query(prompt: str) -> str:
    time_ = get_current_time_info()
    system_prompt = f"""
        {time_}.
        Based on the user's request and provided context, rewrite it into a concise, effective English search query.

        Input from conversation:
        {prompt}

        Rules:
        - If the request is vague (e.g., "search for me"), use the given context to infer the actual intent.
        - Optimize phrasing for reliable sources (e.g., VnExpress, Reuters, Bloomberg).
        - Avoid vague or unrelated terms.
        - Output only the search query.
    """


    try:
        session = await SessionManager.get_session()
        payload = {
            "model": "4T",
            "messages": [
                {"role": "user", "content": system_prompt}
            ],
            "stream": False,
            "options": {"num_keep": 0, "num_predict": 1500, "temperature": 0.2}
        }
        async with session.post(OLLAMA_API_URL, json=payload) as response:
            if response.status != 200:
                logger.error(f"Lỗi API Ollama (generate_search_query): {response.status}")
                return f"{prompt}"  # Fallback query
            data = await response.json()
            query = data['message']['content'].strip()
            logger.info(f"Truy vấn tìm kiếm được tạo: {query}")
            return query
    except Exception as e:
        logger.error(f"Lỗi khi tạo truy vấn tìm kiếm: {e}")
        return f"{prompt}"  # Fallback query

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
