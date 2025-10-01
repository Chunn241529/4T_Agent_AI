# app/utils/embed.py
import numpy as np
from app.services.session_manager import SessionManager
from app.utils.logger import logger

async def embed_text(text: str) -> np.ndarray | None:
    """Embed text dùng Ollama /api/embeddings, trả np.ndarray hoặc None nếu lỗi."""
    try:
        session = await SessionManager.get_session()
        payload = {"model": "embeddinggemma:latest", "prompt": text}
        async with session.post("http://localhost:11434/api/embeddings", json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return np.array(data["embedding"], dtype="float32")
    except Exception as e:
        logger.error(f"Lỗi embed text: {e}")
        return None
