# app/models.py
from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    prompt: str
    model: str = "llama3.2"
    image: Optional[str] = None  # Thêm field image base64
