from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import httpx
import json
import logging
import uvicorn

# Cấu hình logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

OLLAMA_API_URL = "http://localhost:11434/api/chat"

# Pydantic model để validate request body
class ChatRequest(BaseModel):
    content: str

async def stream_ollama_chat(messages: List[dict]):
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0)) as client:
            async with client.stream(
                "POST",
                OLLAMA_API_URL,
                json={
                    "model": "gpt-oss:20b",
                    "messages": messages,
                    "stream": True
                }
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        # Validate JSON cơ bản
                        json.loads(line)
                        # Yield raw JSON string
                        yield line + "\n"  # Thêm newline để giữ định dạng JSON Lines
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON: {line}, error: {e}")
                        continue
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error from Ollama API: {e}")
        raise HTTPException(status_code=502, detail="Error communicating with Ollama API")
    except httpx.RequestError as e:
        logger.error(f"Request error: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to Ollama API")

@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        # Tạo messages array từ content
        messages = [{"role": "user", "content": request.content}]
        return StreamingResponse(
            stream_ollama_chat(messages),
            media_type="application/json"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    uvicorn.run("test:app", host="0.0.0.0", port=8000, reload=True)
