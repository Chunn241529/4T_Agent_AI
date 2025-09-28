# app/models.py
from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    prompt: str
    image: Optional[str] = None  # Thêm field image base64
