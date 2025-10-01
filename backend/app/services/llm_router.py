import re
import base64
import json
from typing import Optional, Set, List
from app.utils.logger import logger
from app.services.get_time import get_current_time_info
from app.services.session_manager import SessionManager
from app.services.memory_manager import HybridMemory

OLLAMA_API_URL = "http://localhost:11434/api/chat"
model_check = "4T-Base"  # Sử dụng model nhỏ hơn cho routing

# Từ khóa cho tìm kiếm web
SEARCH_KEYWORDS = {
    'search', 'tìm', 'tra', 'lookup', 'find',
    'tin tức', 'news', 'mới nhất', 'latest',
    'giá', 'price', 'bao nhiêu', 'how much',
    'hiện tại', 'now', 'current', 'hôm nay', 'today',
    'update', 'cập nhật', 'thời sự', 'thông tin',
    'thị trường', 'market', 'triển khai', 'deploy',
    'version', 'phiên bản', 'trending', 'xu hướng',
    'stock', 'chứng khoán', 'cryptocurrency', 'crypto',
    'weather', 'thời tiết', 'forecast', 'dự báo',
    'địa điểm', 'location', 'nơi đâu', 'where',
    'sự kiện', 'event', 'gần đây', 'recent'
}

# Từ khóa phủ định
NEGATIVE_KEYWORDS = {
    'không', 'đừng', 'no', 'don\'t', 'không cần', 'không muốn',
    'chỉ', 'thôi', 'đơn giản', 'offline', 'không tra', 'không tìm',
    'không tra cứu', 'không cần tìm kiếm', 'không cần tra', 'không search'
}

# Từ khóa xã giao
SOCIAL_KEYWORDS = {
    'chào', 'hello', 'hi', 'hey', 'xin chào',
    'mình là', 'tôi là', 'giúp gì', 'bạn là', 'làm gì',
    'ok', 'thanks', 'cảm ơn', 'hỏi thăm', 'giới thiệu'
}

# Từ khóa kích hoạt suy luận
THINKING_TRIGGER_KEYWORDS = {
    'phân tích', 'suy nghĩ', 'nghiên cứu', 'tối ưu', 'suy luận',
    'cải thiện', 'lập luận', 'cải tiến', 'xây dựng', 'thiết kế',
    'tính toán', 'calculate', 'toán', 'math', 'logic', 'chiến lược', 'strategy',
    'phân loại', 'classify', 'dự đoán', 'predict',
    'code', 'mã', 'program', 'programming', 'reasoning', 'thinking', 'analyze'
}

# Cache cho quyết định
search_decision_cache: dict = {}
thinking_decision_cache: dict = {}

# Khởi tạo HybridMemory
memory = HybridMemory()

def _quick_search_check(prompt: str) -> bool:
    """Kiểm tra nhanh xem prompt có yêu cầu tìm kiếm web hay không."""
    prompt_lower = prompt.lower()

    # Kiểm tra cache
    if prompt_lower in search_decision_cache:
        logger.debug(f"Sử dụng cache cho tìm kiếm: {prompt_lower} -> {search_decision_cache[prompt_lower]}")
        return search_decision_cache[prompt_lower]

    # Kiểm tra từ khóa phủ định
    if any(kw in prompt_lower for kw in NEGATIVE_KEYWORDS):
        logger.info(f"Bỏ qua tìm kiếm do từ khóa phủ định: {prompt_lower}")
        search_decision_cache[prompt_lower] = False
        return False

    # Kiểm tra các mẫu câu xã giao hoặc giới thiệu
    if any(kw in prompt_lower for kw in SOCIAL_KEYWORDS) or re.match(r'^(hi|hello|hey|chào|xin chào|test|ok|thanks|cảm ơn)$', prompt_lower):
        logger.info(f"Bỏ qua tìm kiếm do câu xã giao: {prompt_lower}")
        search_decision_cache[prompt_lower] = False
        return False

    # Kiểm tra từ khóa tìm kiếm
    has_search_keywords = any(kw in prompt_lower for kw in SEARCH_KEYWORDS)
    if has_search_keywords:
        search_decision_cache[prompt_lower] = True
        return True

    # Kiểm tra mẫu câu hỏi, nhưng yêu cầu ngữ cảnh cụ thể
    if re.search(r'\b(ai|bao nhiêu|ở đâu|nơi nào|khi nào|thế nào|làm sao)\b|\?', prompt_lower):
        # Kiểm tra ngữ cảnh lịch sử nếu prompt ngắn
        if len(prompt.split()) < 6:
            recent_messages = " ".join(
                [msg.get("content", "") for msg in memory.short_history if isinstance(msg, dict) and "role" in msg and msg["role"] == "user"][-2:]
            ).lower()
            if any(kw in recent_messages for kw in SEARCH_KEYWORDS):
                search_decision_cache[prompt_lower] = True
                return True
            else:
                logger.info(f"Bỏ qua tìm kiếm do thiếu ngữ cảnh tìm kiếm: {prompt_lower}")
                search_decision_cache[prompt_lower] = False
                return False
        else:
            search_decision_cache[prompt_lower] = True
            return True

    # Mặc định không tìm kiếm
    search_decision_cache[prompt_lower] = False
    return False

def _quick_thinking_check(prompt: str) -> bool:
    """Kiểm tra nhanh xem prompt có yêu cầu suy luận sâu hay không."""
    prompt_lower = prompt.lower()

    # Kiểm tra cache
    if prompt_lower in thinking_decision_cache:
        logger.debug(f"Sử dụng cache cho suy luận: {prompt_lower} -> {thinking_decision_cache[prompt_lower]}")
        return thinking_decision_cache[prompt_lower]

    # Kiểm tra từ khóa phủ định
    if any(kw in prompt_lower for kw in NEGATIVE_KEYWORDS):
        logger.info(f"Bỏ qua suy luận do từ khóa phủ định: {prompt_lower}")
        thinking_decision_cache[prompt_lower] = False
        return False

    # Kiểm tra các mẫu câu xã giao hoặc đơn giản
    if any(kw in prompt_lower for kw in SOCIAL_KEYWORDS) or re.match(r'^(hi|hello|hey|chào|xin chào|test|ok|thanks|cảm ơn)$', prompt_lower):
        logger.info(f"Bỏ qua suy luận do câu xã giao: {prompt_lower}")
        thinking_decision_cache[prompt_lower] = False
        return False

    # Kiểm tra từ khóa suy luận
    has_thinking_keywords = any(kw in prompt_lower for kw in THINKING_TRIGGER_KEYWORDS)
    if has_thinking_keywords:
        thinking_decision_cache[prompt_lower] = True
        return True

    # Kiểm tra mẫu yêu cầu phức tạp
    if re.search(r'\b(code|mã|program|programming|tính toán|phân tích|giải thích|đánh giá|so sánh|thiết kế)\b', prompt_lower):
        thinking_decision_cache[prompt_lower] = True
        return True

    # Kiểm tra độ dài và ngữ cảnh lịch sử
    if len(prompt.split()) > 8:
        recent_messages = " ".join(
            [msg.get("content", "") for msg in memory.short_history if isinstance(msg, dict) and "role" in msg and msg["role"] == "user"][-2:]
        ).lower()
        if any(kw in recent_messages for kw in THINKING_TRIGGER_KEYWORDS):
            thinking_decision_cache[prompt_lower] = True
            return True

    # Mặc định không suy luận
    thinking_decision_cache[prompt_lower] = False
    return False

async def should_search_web(prompt: str) -> bool:
    """Quyết định xem có nên tìm kiếm web dựa trên prompt."""
    result = _quick_search_check(prompt)
    logger.info(f"Quyết định tìm kiếm web: {result} cho prompt: {prompt[:50]}...")
    return result

async def should_thinking(messages_for_llm: List[dict]) -> bool:
    """Quyết định xem có nên dùng chế độ suy luận dựa trên prompt."""
    # Lấy prompt từ tin nhắn cuối cùng của user
    user_msg = next((msg for msg in reversed(messages_for_llm) if msg["role"] == "user"), None)
    if not user_msg or not isinstance(user_msg, dict) or "content" not in user_msg:
        logger.warning("Không tìm thấy tin nhắn user hợp lệ trong messages_for_llm")
        return False

    prompt = user_msg["content"]
    result = _quick_thinking_check(prompt)
    logger.info(f"Quyết định suy luận: {result} cho prompt: {prompt[:50]}...")
    return result

async def generate_search_query(prompt: str) -> str:
    time_ = get_current_time_info()
    _prompt = f"""
        {time_}.
        Based on the user's request and provided context, rewrite it into a concise, effective English search query.

        Input from conversation:
        {prompt}

        Rules:
        - Use the given context to infer the actual intent.
        - Optimize phrasing for reliable sources.
        - Avoid vague or unrelated terms.
        - Output only the search query. NO Title.
    """

    try:
        session = await SessionManager.get_session()
        payload = {
            "model": model_check,
            "messages": [
                {"role": "user", "content": _prompt}
            ],
            "stream": False,
            "options": {"num_predict": 500, "temperature": 0.001}
        }
        async with session.post(OLLAMA_API_URL, json=payload) as response:
            response.raise_for_status()
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
