# app/models.py

from pydantic import BaseModel

class ChatRequest(BaseModel):
    prompt: str
    model: str = "gemma3:4b"
