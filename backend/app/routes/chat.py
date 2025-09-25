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
from app.services.llm_router import should_search_web, generate_search_query, decode_base64_image
import aiohttp
from datetime import datetime
import pytz

router = APIRouter(prefix="/api")
OLLAMA_API_URL = "http://localhost:11434/api/chat"

@router.post("/chat")
async def chat(request: ChatRequest):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt không được để trống")

    async def response_generator():
        try:
            # Kiểm tra và xử lý hình ảnh nếu có
            image_description = ""
            image_base64 = None
            if request.image:
                try:
                    # Làm sạch base64 và kiểm tra tính hợp lệ
                    image_base64 = request.image
                    if image_base64.startswith('data:image'):
                        image_base64 = image_base64.split(',')[1]
                    image_bytes = base64.b64decode(image_base64)
                    if len(image_bytes) > 20 * 1024 * 1024:  # 20MB
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
                            "model": "gemma3:4b",
                            "messages": [{
                                "role": "user",
                                "content": "Hãy mô tả chi tiết bằng tiếng Việt những gì bạn thấy trong ảnh này. Giữ ngắn gọn trong 800 ký tự. Không nói những câu thừa thải. Không tiêu đề. Chỉ trả ra mô tả.",
                                "images": [image_base64]
                            }],
                            "stream": True,
                            "options": {"num_keep": 0, "num_predict": 500, "temperature": 0.2}
                        }
                        async with session.post(OLLAMA_API_URL, json=payload) as response:
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

            # Thêm mô tả ảnh vào prompt để quyết định tìm kiếm
            search_prompt = f"{prompt}\n\n[Mô tả ảnh: {image_description}]" if image_description else prompt

            # Xác định có cần tìm kiếm web không
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
                search_query = await generate_search_query(search_query)
                web_results = await search_web(search_query)
                if web_results:
                    sources = [{"url": res["url"], "title": res["title"]} for res in web_results[:3]]
                    web_context = "\n\n".join([
                        f"### Nguồn: {res['title']}\n**URL**: {res['url']}\n**Nội dung**: {res['content'][:500]}"
                        for res in web_results[:3]
                    ])

            yield json.dumps({"type": "sources", "sources": sources}).encode('utf-8') + b'\n'

            # Giai đoạn 2: Tạo câu trả lời cuối với gemma3:4b
            # Lấy thời gian hiện tại
            tz = pytz.timezone('Asia/Ho_Chi_Minh')
            now = datetime.now(tz)
            day_name = ['Thứ Hai', 'Thứ Ba', 'Thứ Tư', 'Thứ Năm', 'Thứ Sáu', 'Thứ Bảy', 'Chủ Nhật'][now.weekday()]
            current_time = now.strftime("%H:%M (GMT+7), %d/%m/%Y")
            time_string = f"Hiện tại là {current_time}, {day_name}. (bạn không cần nhắc lại phần này) "

            full_prompt = f"""
                {time_string}.
                Bạn là '4T', một trợ lý AI hữu ích.
                Trả lời bằng tiếng Việt, định dạng markdown (sử dụng tiêu đề, gạch đầu dòng, trích dẫn nguồn nếu có).
                Câu trả lời phải:
                - Ngắn gọn nhưng đầy đủ chi tiết quan trọng
                - Chính xác, dựa trên ngữ cảnh
                - Trích dẫn nguồn [Nguồn](url) nếu thông tin đến từ web_context
                - Nếu không có web_context thì trả lời dựa trên kiến thức nội tại

                {f"### Mô tả ảnh (thông tin do hệ thống phân tích, không phải do người dùng nhập):\n{image_description}\n" if image_description else ""}

                ### Ngữ cảnh từ kết quả tìm kiếm web (do hệ thống tự động thu thập, KHÔNG phải do người dùng cung cấp):
                {web_context}
            """

            yield json.dumps({"type": "content_start"}).encode('utf-8') + b'\n'

            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": "gemma3:4b",
                    "messages": [
                        {"role": "system", "content": full_prompt},
                        {"role": "user", "content": f"### Câu hỏi của người dùng:\n{prompt}"}
                    ],
                    "stream": True,
                    "options": {"temperature": 0.7, "num_predict": -1}
                }
                async with session.post(OLLAMA_API_URL, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Lỗi API Ollama (trả lời): {response.status}")
                        error_message = f"### Lỗi\nKhông thể xử lý yêu cầu do lỗi server"
                        yield json.dumps({"type": "error", "message": {"content": error_message}}).encode('utf-8') + b'\n'
                        return

                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                if 'message' in data and 'content' in data['message']:
                                    content = data['message']['content']
                                    yield json.dumps({"type": "content", "message": {"content": content}}).encode('utf-8') + b'\n'
                            except json.JSONDecodeError as e:
                                logger.error(f"Lỗi giải mã JSON: {e}")
                                yield json.dumps({"type": "error", "message": {"content": f"### Lỗi\nLỗi giải mã dữ liệu: {str(e)}"}}).encode('utf-8') + b'\n'
                            finally:
                                gc.collect()  # Cleanup sau mỗi chunk
        except Exception as e:
            logger.error(f"Lỗi khi xử lý chat: {e}")
            error_message = f"### Lỗi\nKhông thể xử lý yêu cầu do: {str(e)}"
            yield json.dumps({"type": "error", "message": {"content": error_message}}).encode('utf-8') + b'\n'
        finally:
            gc.collect()
            logger.info("Hoàn tất xử lý chat và cleanup bộ nhớ")

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")