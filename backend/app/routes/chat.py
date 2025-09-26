# app/routes/chat.py
import re
import unicodedata
from app.utils.logger import logger
import json
import base64
import gc
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models import ChatRequest
from app.services.web_searcher import search_web
from app.services.llm_router import should_search_web, generate_search_query
import aiohttp
from app.services.get_time import get_current_time_info

router = APIRouter(prefix="/api")
OLLAMA_API_URL = "http://localhost:11434/api"
current_model = "4T-S"
vision_model = "4T-V"
brief_history_model = "4T-S"
history = []  # Danh sách lưu lịch sử hội thoại

# --- CẢI TIẾN: Thêm ngưỡng kích hoạt tóm tắt ---
HISTORY_SUMMARY_THRESHOLD = 2048  # Kích hoạt tóm tắt nếu history vượt quá 2048 tokens (ước tính)

# --- CẢI TIẾN: Hàm ước tính token ---
def _estimate_token_count(messages: list[dict]) -> int:
    """Ước tính tổng số token trong danh sách messages một cách đơn giản."""
    total_tokens = 0
    for message in messages:
        # Heuristic: 1 token ~ 3 ký tự tiếng Việt. Đây là cách ước tính nhanh.
        content = message.get("content", "")
        if content:
            total_tokens += len(content) // 3
    return total_tokens

async def summarize_history(session, past_conversations: list, prompt: str) -> str:
    """
    Tóm tắt lịch sử hội thoại sử dụng LLM.
    """
    if not past_conversations:
        return ""

    past_messages_flat = [msg for conv in past_conversations for msg in conv]
    history_str = "\n\n".join([
        f"[{msg['role'].capitalize()}]: {msg['content']}"
        for msg in past_messages_flat
        if msg["role"] in ["user", "assistant"]
    ])

    summary_prompt = f"""
    Tóm tắt ngắn gọn lịch sử hội thoại sau bằng tiếng Việt, tập trung vào các điểm chính liên quan đến yêu cầu hiện tại '{prompt}':
    {history_str}
    Tóm tắt phải ngắn, chỉ giữ thông tin cần thiết.
    """

    payload = {
        "model": brief_history_model,
        "messages": [{"role": "user", "content": summary_prompt}],
        "stream": False,
        "options": {"temperature": 0.5, "num_predict": 1000}
    }

    async with session.post(f"{OLLAMA_API_URL}/chat", json=payload) as response:
        if response.status == 200:
            data = await response.json()
            summary = data.get("message", {}).get("content", "").strip()
            logger.info(f"Tóm tắt lịch sử: {summary[:50]}...")
            return summary
        else:
            logger.error(f"Lỗi tóm tắt lịch sử: {response.status}")
            return ""

@router.post("/chat")
async def chat(request: ChatRequest):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt không được để trống")

    async def response_generator():
        try:
            # Xử lý hình ảnh (giữ nguyên logic cũ)
            image_description = ""
            image_base64 = None
            if request.image:
                try:
                    image_base64 = request.image
                    if image_base64.startswith('data:image'):
                        image_base64 = image_base64.split(',')[1]
                    image_bytes = base64.b64decode(image_base64)
                    if len(image_bytes) > 20 * 1024 * 1024:
                        logger.warning("Hình ảnh quá lớn, vượt quá 20MB")
                        yield json.dumps({"type": "error", "message": {"content": "Hình ảnh quá lớn, vượt quá giới hạn 20MB"}}).encode('utf-8') + b'\n'
                        return
                except base64.binascii.Error:
                    logger.warning("Chuỗi base64 không hợp lệ")
                    image_description = "[Không thể xử lý ảnh]"
                    image_base64 = None

            if image_base64:
                try:
                    yield json.dumps({"type": "image_processing"}).encode('utf-8') + b'\n'
                    async with aiohttp.ClientSession() as session:
                        payload = {
                            "model": vision_model,
                            "messages": [{
                                "role": "user",
                                "content": "Hãy mô tả chi tiết bằng tiếng Việt những gì bạn thấy trong ảnh này. Không nói những câu thừa thải. Không tiêu đề. Chỉ trả ra mô tả.",
                                "images": [image_base64]
                            }],
                            "stream": True,
                            "options": {"num_keep": 0, "num_predict": 800, "temperature": 0.2}
                        }
                        async with session.post(f"{OLLAMA_API_URL}/chat", json=payload) as response:
                            if response.status != 200:
                                logger.error(f"Lỗi API Ollama (ảnh): {response.status}")
                                image_description = "[Không thể xử lý ảnh]"
                                yield json.dumps({"type": "image_description", "content": image_description}).encode('utf-8') + b'\n'
                            else:
                                last_char = ""  # Theo dõi ký tự cuối của chunk trước
                                async for line in response.content:
                                    if line:
                                        try:
                                            data = json.loads(line.decode('utf-8'))
                                            if 'message' in data and 'content' in data['message']:
                                                chunk = data['message']['content'].strip()
                                                if chunk:
                                                    # Làm sạch chunk: chuẩn hóa Unicode, loại bỏ ký tự điều khiển
                                                    chunk = unicodedata.normalize('NFKC', chunk)
                                                    chunk = re.sub(r'[\x00-\x1F\x7F]+', '', chunk)  # Loại bỏ control chars
                                                    chunk = re.sub(r'\s+', ' ', chunk).strip()  # Chuẩn hóa khoảng trắng

                                                    # Thêm dấu cách nếu chunk trước và chunk hiện tại dính nhau
                                                    if last_char and chunk and last_char.isalnum() and chunk[0].isalnum():
                                                        image_description += " "
                                                    image_description += chunk
                                                    last_char = chunk[-1] if chunk else ""

                                                    # Giới hạn độ dài
                                                    if len(image_description) > 800:
                                                        image_description = image_description[:800]
                                                        last_char = image_description[-1]

                                                    # Gửi chunk đã làm sạch
                                                    yield json.dumps({"type": "image_description", "content": chunk}).encode('utf-8') + b'\n'
                                                    logger.debug(f"Chunk ảnh: {chunk[:50]}...")
                                        except json.JSONDecodeError as e:
                                            logger.error(f"Lỗi giải mã JSON (ảnh): {e}")
                                            continue
                                logger.info(f"Mô tả ảnh hoàn tất: {image_description[:50]}...")
                    gc.collect()
                    logger.info("Đã xử lý ảnh và cleanup bộ nhớ")
                except Exception as e:
                    logger.error(f"Lỗi khi xử lý ảnh: {e}")
                    image_description = "[Không thể xử lý ảnh]"
                    yield json.dumps({"type": "image_description", "content": image_description}).encode('utf-8') + b'\n'

            # --- CẢI TIẾN: Thay RAG bằng tóm tắt cho search_prompt và history_context ---
            history_summary = ""
            async with aiohttp.ClientSession() as session:
                past_conversations = history[:-1] if history else []
                past_messages_flat = [msg for conv in past_conversations for msg in conv]
                history_tokens = _estimate_token_count(past_messages_flat)


                logger.info("Lịch sử dài, tóm tắt lịch sử cho search_prompt và history_context.")
                history_summary = await summarize_history(session, past_conversations, prompt)

                # Làm sạch history_summary
                history_summary = unicodedata.normalize('NFKC', history_summary) if history_summary else ""
                history_summary = re.sub(r'[\x00-\x1F\x7F]+', '', history_summary)
                history_summary = re.sub(r'\s+', ' ', history_summary).strip()
                logger.info(f"Đã tạo history_summary: {history_summary[:50]}...")

            # Tạo search_prompt với tóm tắt
            search_prompt = f"{prompt}\n\n[Mô tả ảnh: {image_description}]" if image_description else prompt
            if history_summary:
                search_prompt += f"\n\n[Ngữ cảnh lịch sử liên quan]: {history_summary}"

            sources = []
            if prompt.lower().startswith("/search"):
                search_query = prompt[7:].strip()
                perform_search = True
            else:
                perform_search = await should_search_web(search_prompt)
                search_query = prompt

            # Tìm kiếm web nếu cần
            web_context = ""
            if perform_search:
                yield json.dumps({"type": "search_start"}).encode('utf-8') + b'\n'
                # --- CẢI TIẾN: Thêm history_summary vào search_query ---
                search_query_input = f"{search_query}\n\n[Ngữ cảnh lịch sử liên quan]: {history_summary}" if history_summary else search_query
                logger.debug(f"Input cho generate_search_query: {search_query_input[:100]}...")
                search_query = await generate_search_query(search_query_input)
                web_results = await search_web(search_query)
                if web_results:
                    sources = [{"url": res["url"], "title": res["title"]} for res in web_results[:3]]
                    web_context = "\n\n".join([
                        f"### Nguồn: {res['title']}\n**URL**: {res['url']}\n**Nội dung**: {res['content']}"
                        for res in web_results[:3]
                    ])

            yield json.dumps({"type": "sources", "sources": sources}).encode('utf-8') + b'\n'

            time_string = get_current_time_info()
            full_system = f"""
                Thời gian hiện tại là: `{time_string}`.
                Bạn là '4T', một trợ lý AI hữu ích.
                Trả lời bằng tiếng Việt, định dạng markdown (sử dụng tiêu đề, gạch đầu dòng, trích dẫn nguồn nếu có).
                Câu trả lời phải:
                - Ngắn gọn nhưng đầy đủ chi tiết quan trọng
                - Chính xác, dựa trên ngữ cảnh
                - Trích dẫn nguồn [Nguồn](url) nếu thông tin đến từ web_context
                - Nếu không có web_context thì trả lời dựa trên kiến thức nội tại

                {f"### Mô tả ảnh (thông tin do hệ thống phân tích, không phải do người dùng nhập):\n{image_description}\n" if image_description else ""}

                ### Ngữ cảnh từ kết quả tìm kiếm web (do hệ thống tự động thu thập, KHÔNG phải do người dùng cung cấp):
                web_context: {web_context}
            """

            history.append([
                {"role": "system", "content": full_system},
                {"role": "user", "content": prompt}
            ])
            logger.info(f"Đã lưu system và user prompt vào lịch sử: {prompt[:50]}...")

            yield json.dumps({"type": "content_start"}).encode('utf-8') + b'\n'

            # --- CẢI TIẾN: LOGIC TÓM TẮT DỰA TRÊN NGƯỠNG TOKEN ---
            async with aiohttp.ClientSession() as session:
                messages_for_llm = []

                current_system_prompt = history[-1][0]
                current_user_prompt = history[-1][1]
                past_conversations = history[:-1]

                past_messages_flat = [msg for conv in past_conversations for msg in conv]
                history_tokens = _estimate_token_count(past_messages_flat)
                logger.info(f"Ước tính token của lịch sử: {history_tokens}. Ngưỡng tóm tắt: {HISTORY_SUMMARY_THRESHOLD}")

                if not past_conversations or history_tokens <= HISTORY_SUMMARY_THRESHOLD:
                    logger.info("Lịch sử ngắn, sử dụng toàn bộ context.")
                    messages_for_llm.append(current_system_prompt)
                    messages_for_llm.extend(past_messages_flat)
                    messages_for_llm.append(current_user_prompt)
                else:
                    logger.info("Lịch sử dài, tóm tắt lịch sử.")
                    yield json.dumps({"type": "summary_status", "message": "Lịch sử dài, đang tóm tắt..."}).encode('utf-8') + b'\n'

                    summary = await summarize_history(session, past_conversations, prompt)
                    summary_message = {"role": "system", "content": f"Tóm tắt lịch sử: {summary}"}

                    messages_for_llm.append(current_system_prompt)
                    messages_for_llm.append(summary_message)
                    messages_for_llm.append(current_user_prompt)

            if not messages_for_llm or not all(isinstance(msg, dict) and "role" in msg and "content" in msg for msg in messages_for_llm):
                logger.error("Danh sách messages không hợp lệ để gửi đến LLM")
                error_message = "### Lỗi\nLỗi hệ thống: Không thể xây dựng ngữ cảnh hợp lệ."
                yield json.dumps({"type": "error", "message": {"content": error_message}}).encode('utf-8') + b'\n'
                return

            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": current_model,
                    "messages": messages_for_llm,
                    "stream": True,
                    "options": {"temperature": 0.7, "num_predict": -1}
                }
                logger.debug(f"Payload gửi đến API Ollama: {json.dumps(payload, ensure_ascii=False)[:300]}...")
                response_content = ""
                async with session.post(f"{OLLAMA_API_URL}/chat", json=payload) as response:
                    if response.status != 200:
                        error_detail = await response.text()
                        logger.error(f"Lỗi API Ollama (trả lời): {response.status}, Chi tiết: {error_detail}")
                        error_message = f"### Lỗi\nKhông thể xử lý yêu cầu do lỗi server: {error_detail}"
                        yield json.dumps({"type": "error", "message": {"content": error_message}}).encode('utf-8') + b'\n'
                        return

                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                if 'message' in data and 'content' in data['message']:
                                    content = data['message']['content']
                                    response_content += content
                                    yield json.dumps({"type": "content", "message": {"content": content}}).encode('utf-8') + b'\n'
                            except json.JSONDecodeError as e:
                                logger.error(f"Lỗi giải mã JSON: {e}")
                                continue

                    if response_content:
                        history[-1].append({"role": "assistant", "content": response_content})
                        logger.info(f"Hoàn tất lưu câu trả lời vào lịch sử: {response_content[:50]}...")

        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng khi xử lý chat: {e}", exc_info=True)
            error_message = f"### Lỗi\nĐã có lỗi không mong muốn xảy ra: {str(e)}"
            yield json.dumps({"type": "error", "message": {"content": error_message}}).encode('utf-8') + b'\n'
        finally:
            gc.collect()
            logger.info("Hoàn tất xử lý yêu cầu chat và cleanup bộ nhớ")

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")
