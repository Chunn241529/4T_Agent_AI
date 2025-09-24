from asyncio.log import logger
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models import ChatRequest
from app.services.web_searcher import search_web
from app.services.llm_router import should_search_web, generate_search_query
import ollama

router = APIRouter(prefix="/api")

@router.post("/chat")
async def chat(request: ChatRequest):
    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt không được để trống")

    async def response_generator():
        try:
            sources = []
            if prompt.lower().startswith("/search"):
                search_query = prompt[7:].strip()
                perform_search = True
            else:
                perform_search = await should_search_web(prompt)
                search_query = prompt

            web_context = ""
            if perform_search:
                logger.info("Gửi search_start")  # Thêm log
                yield json.dumps({"type": "search_start"}).encode('utf-8') + b'\n'
                
                search_query = await generate_search_query(search_query)
                web_results = await search_web(search_query)
                if web_results:
                    sources = [{"url": res["url"], "title": res["title"]} for res in web_results]
                    web_context = "\n\n".join([
                        f"### Nguồn: {res['title']}\n**URL**: {res['url']}\n**Nội dung**: {res['content'][:1500]}"
                        for res in web_results
                    ])

            logger.info(f"Gửi sources: {sources}")  # Thêm log
            yield json.dumps({"type": "sources", "sources": sources}).encode('utf-8') + b'\n'

            full_prompt = f"""
            Bạn là một trợ lý AI hữu ích. Hãy trả lời câu hỏi của người dùng bằng tiếng Việt, định dạng câu trả lời dưới dạng markdown (sử dụng tiêu đề, gạch đầu dòng, và trích dẫn nguồn nếu có). 
            Câu trả lời phải ngắn gọn, chính xác, đầy đủ chi tiết, và dựa trên ngữ cảnh được cung cấp.
            Nếu sử dụng thông tin từ web, trích dẫn nguồn bằng [Nguồn](url).
            Nếu không có thông tin web, trả lời dựa trên kiến thức nội tại. Và không nói gì thêm về thông tin web.

            ### Ngữ cảnh
            {web_context}

            ### Câu hỏi
            {prompt}
            """

            logger.info("Gửi content_start")  # Thêm log
            yield json.dumps({"type": "content_start"}).encode('utf-8') + b'\n'

            stream = await ollama.AsyncClient().chat(
                model=request.model,
                messages=[{"role": "user", "content": full_prompt}],
                stream=True
            )
            async for chunk in stream:
                if 'message' in chunk and 'content' in chunk['message']:
                    content = chunk['message']['content']
                    # logger.info(f"Gửi content chunk: {content[:50]}...")  # Thêm log
                    yield json.dumps({"type": "content", "message": {"content": content}}).encode('utf-8') + b'\n'
        except Exception as e:
            logger.error(f"Lỗi khi xử lý chat: {e}")
            error_message = f"### Lỗi\nKhông thể xử lý yêu cầu do: {str(e)}"
            logger.info("Gửi error")  # Thêm log
            yield json.dumps({"type": "error", "message": {"content": error_message}}).encode('utf-8') + b'\n'

    return StreamingResponse(response_generator(), media_type="application/x-ndjson")