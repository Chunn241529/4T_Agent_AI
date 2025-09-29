import re
import asyncio
import unicodedata
from app.utils.logger import logger
import json
import base64
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models import ChatRequest
from app.services.web_searcher import search_web
from app.services.llm_router import should_search_web, should_thinking, generate_search_query
from app.services.session_manager import SessionManager
from app.services.get_time import get_current_time_info
from app.services.summarize_history import summarize_history
from pydantic import BaseModel
from typing import Optional, Dict, List
from datetime import datetime, timedelta

# Import HybridMemory
from app.services.memory_manager import HybridMemory

router = APIRouter(prefix="/api")
OLLAMA_API_URL = "http://localhost:11434/api"
vision_model = "4T-V"

# Hybrid memory thay cho CONTEXT_MESSAGES
memory = HybridMemory(dim=1024, max_short=20)

class ChatRequest(BaseModel):
    prompt: str
    image: str | None = None
    is_thinking: bool = False

class ChunkBuffer:
    def __init__(self, size: int = 200):
        self.buffer = ""
        self.size = size

    def add(self, chunk: str) -> Optional[str]:
        self.buffer += chunk
        if len(self.buffer) >= self.size:
            result = self.buffer
            self.buffer = ""
            return result
        return None

    def flush(self) -> Optional[str]:
        if self.buffer:
            result = self.buffer
            self.buffer = ""
            return result
        return None

def _safe_json_dumps(data: dict) -> bytes:
    try:
        json_str = json.dumps(data, ensure_ascii=False)
        logger.debug(f"Chuẩn bị gửi JSON chunk: {json_str[:100]}...")
        return json_str.encode('utf-8') + b'\n'
    except Exception as e:
        logger.error(f"Lỗi khi encode JSON: {e}")
        return json.dumps({"type": "error", "message": {"content": f"Lỗi hệ thống khi encode JSON: {str(e)}"}}).encode('utf-8') + b'\n'

@router.post("/chat")
async def chat(request: ChatRequest):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt không được để trống")

    async def response_generator():
        try:
            # Khởi tạo các biến cơ bản
            is_thinking = request.is_thinking
            current_model = "kimi-k2:1t-cloud"

            # 1. XỬ LÝ HÌNH ẢNH
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
                        image_description = "[Hình ảnh quá lớn, vượt quá giới hạn 20MB]"
                        yield _safe_json_dumps({"type": "error", "message": {"content": "Hình ảnh quá lớn, vượt quá giới hạn 20MB"}})
                        return
                except base64.binascii.Error:
                    logger.warning("Chuỗi base64 không hợp lệ")
                    image_description = "[Không thể xử lý ảnh]"
                    image_base64 = None

            if image_base64:
                try:
                    yield _safe_json_dumps({"type": "image_processing"})
                    session = await SessionManager.get_session()
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
                            yield _safe_json_dumps({"type": "image_description", "content": image_description})
                        else:
                            last_char = ""
                            async for line in response.content:
                                if not line.strip():
                                    continue
                                try:
                                    data = json.loads(line.decode('utf-8'))
                                    if 'message' in data and 'content' in data['message']:
                                        chunk = data['message']['content']
                                        if chunk:
                                            chunk = unicodedata.normalize('NFKC', chunk)
                                            if last_char and chunk and last_char.isalnum() and chunk[0].isalnum():
                                                image_description += " "
                                            image_description += chunk
                                            last_char = chunk[-1] if chunk else ""
                                            if len(image_description) > 800:
                                                image_description = image_description[:800]
                                                last_char = image_description[-1]
                                            yield _safe_json_dumps({"type": "image_description", "content": chunk})
                                    else:
                                        logger.warning(f"Dữ liệu Ollama (ảnh) không có message.content: {line.decode('utf-8')[:100]}")
                                        yield _safe_json_dumps({
                                            "type": "error",
                                            "message": {"content": f"Dữ liệu không hợp lệ từ Ollama (ảnh): {line.decode('utf-8')[:100]}"}
                                        })
                                except json.JSONDecodeError as e:
                                    logger.error(f"Lỗi giải mã JSON (ảnh): {e}, Raw line: {line.decode('utf-8')[:100]}")
                                    chunk = line.decode('utf-8')
                                    if chunk:
                                        chunk = unicodedata.normalize('NFKC', chunk)
                                        yield _safe_json_dumps({"type": "image_description", "content": chunk})
                                    else:
                                        yield _safe_json_dumps({
                                            "type": "error",
                                            "message": {"content": f"Lỗi giải mã JSON từ Ollama (ảnh): {line.decode('utf-8')[:100]}"}
                                        })
                                    continue
                            logger.info(f"Mô tả ảnh hoàn tất: {image_description[:50]}...")
                except Exception as e:
                    logger.error(f"Lỗi khi xử lý ảnh: {e}")
                    image_description = "[Không thể xử lý ảnh]"
                    yield _safe_json_dumps({"type": "image_description", "content": image_description})

            # 2. LOGIC TÌM KIẾM WEB
            sources = []
            web_context = ""
            search_decision_prompt = f"{prompt}\n\n[Mô tả ảnh: {image_description}]" if image_description else prompt

            # Lấy ngữ cảnh gần đây từ short history
            recent_messages = " ".join([msg.get("content", "") for msg in memory.short_history if msg["role"] == "user"])
            if recent_messages:
                search_decision_prompt += f"\n\n[Ngữ cảnh gần đây]: {recent_messages}"

            perform_search = False
            search_query_generation_input = ""
            if prompt.lower().startswith("/search"):
                perform_search = True
                search_query_generation_input = prompt[7:].strip()
                if recent_messages:
                    search_query_generation_input += f"\n\n[Ngữ cảnh]: {recent_messages}"
            else:
                perform_search = await should_search_web(prompt)
                search_query_generation_input = search_decision_prompt

            if perform_search:
                final_search_query = await generate_search_query(search_query_generation_input)
                yield _safe_json_dumps({"type": "search_start", "query": final_search_query})
                web_results = await search_web(final_search_query, mode="rerank")
                logger.debug(f"Input cho generate_search_query: {search_query_generation_input[:100]}...")

                if web_results:
                    sources = [{"url": res["url"], "title": res["title"]} for res in web_results[:3]]
                    web_context = "\n\n".join([
                        f"### Nguồn: {res['title']}\n**URL**: {res['url']}\n**Nội dung**: {res['content']}"
                        for res in web_results[:3]
                    ])

            yield _safe_json_dumps({"type": "sources", "sources": sources})

            # 3. QUYẾT ĐỊNH MODEL
            messages_for_model_decision = [
                {"role": "system", "content": f"Context: {web_context if web_context else ''}\n{image_description if image_description else ''}\n{recent_messages if recent_messages else ''}"},
                {"role": "user", "content": prompt}
            ]
            is_thinking = request.is_thinking or await should_thinking(messages_for_model_decision)
            current_model = "kimi-k2:1t-cloud" if is_thinking else "kimi-k2:1t-cloud"
            logger.info(f"Model được chọn: {current_model} (is_thinking={is_thinking})")

            # 4. SYSTEM PROMPT
            time_string = get_current_time_info()
            full_system = f"""
              {time_string}
              Bạn là **4T**, một trợ lý AI toàn diện.
              Nguyên tắc trả lời:
              - Luôn bằng **tiếng Việt**, định dạng **markdown** (dùng tiêu đề, gạch đầu dòng, trích dẫn nguồn nếu có).
              - Trả lời **ngắn gọn nhưng đủ chi tiết quan trọng**.
              - Nếu có `web_context` thì **ưu tiên dùng** và trích dẫn [Nguồn](url).
              - Nếu không có `web_context` thì dựa trên **kiến thức nội tại**.
              - Nhớ: `web_context`, `image_description` là **do hệ thống cung cấp, không phải người dùng**.
            """

            full_prompt = f"""
            ### Câu hỏi từ người dùng:
            {prompt}

            Hệ thống cung cấp thông tin:
            {f"### Phân tích ảnh:\n{image_description}\n" if image_description else ""}

            {f"### Ngữ cảnh từ tìm kiếm web:\n{web_context}" if web_context else "### Không có web_context, hãy trả lời dựa trên kiến thức nội tại."}
            """

            current_user_msg = {"role": "user", "content": full_prompt}

            # 5. XÂY DỰNG CONTEXT CUỐI
            yield _safe_json_dumps({"type": "content_start"})

            messages_for_llm = [{"role": "system", "content": full_system}]
            mem_context = await memory.build_context(prompt)
            messages_for_llm.extend(mem_context)
            messages_for_llm.append(current_user_msg)

            if not messages_for_llm or not all(isinstance(msg, dict) and "role" in msg and "content" in msg for msg in messages_for_llm):
                logger.error("Danh sách messages không hợp lệ để gửi đến LLM")
                error_message = "### Lỗi\nLỗi hệ thống: Không thể xây dựng ngữ cảnh hợp lệ."
                yield _safe_json_dumps({"type": "error", "message": {"content": error_message}})
                return

            # 6. GỌI LLM
            session = await SessionManager.get_session()
            chunk_buffer = ChunkBuffer()

            payload = {
                "model": current_model,
                "messages": messages_for_llm,
                "stream": True,
                "options": {"temperature": 1, "num_predict": -1}
            }
            response_content = ""
            async with session.post(f"{OLLAMA_API_URL}/chat", json=payload) as response:
                if response.status != 200:
                    error_detail = await response.text()
                    logger.error(f"Lỗi API Ollama: {response.status}, Chi tiết: {error_detail}")
                    yield _safe_json_dumps({"type": "error", "message": {"content": f"Lỗi server: {error_detail}"}})
                    return

                async for line in response.content:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if 'message' in data and 'content' in data['message']:
                            content = data['message']['content']
                            if content:
                                response_content += content
                        yield line
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON from Ollama: {e}")
                        continue

            if response_content:
                await memory.add_message("user", prompt)
                await memory.add_message("assistant", response_content)
                logger.info("Đã cập nhật memory với cặp message mới.")
            else:
                logger.warning("Không nhận được nội dung hợp lệ từ API")
                yield _safe_json_dumps({"type": "error", "message": {"content": "Không nhận được nội dung hợp lệ từ API"}})

        except Exception as e:
            logger.error(f"Lỗi nghiêm trọng khi xử lý chat: {e}", exc_info=True)
            yield _safe_json_dumps({"type": "error", "message": {"content": f"### Lỗi\nĐã có lỗi không mong muốn xảy ra: {str(e)}"}})
        finally:
            if 'chunk_buffer' in locals():
                final_chunk = chunk_buffer.flush()
                if final_chunk:
                    yield _safe_json_dumps({"type": "content", "content": final_chunk})

            logger.info("Hoàn tất xử lý yêu cầu.")

    return StreamingResponse(response_generator(), media_type="application/json")
