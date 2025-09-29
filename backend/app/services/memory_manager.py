# app/services/memory_manager.py
import faiss
import numpy as np
from datetime import datetime
from app.services.session_manager import SessionManager

class HybridMemory:
    def __init__(self, dim=1024, max_short=20):
        self.short_history = []
        self.max_short = max_short
        self.index = faiss.IndexFlatL2(dim)  # FAISS vector store
        self.store = []  # metadata song song với FAISS

    async def embed_text(self, text: str) -> np.ndarray:
        """Gọi Ollama embed API"""
        session = await SessionManager.get_session()
        payload = {"model": "nomic-embed-text", "input": text}
        async with session.post("http://localhost:11434/api/embed", json=payload) as resp:
            data = await resp.json()
            return np.array(data["embeddings"][0], dtype="float32")

    async def add_message(self, role: str, content: str):
        """Lưu message vào short-term, nếu tràn thì đẩy vào FAISS"""
        self.short_history.append({"role": role, "content": content})
        if len(self.short_history) > self.max_short:
            old = self.short_history.pop(0)
            vec = await self.embed_text(old["content"])
            self.index.add(np.expand_dims(vec, 0))
            self.store.append({"role": old["role"], "content": old["content"], "time": datetime.utcnow()})

    async def retrieve(self, query: str, k=5):
        """Semantic search từ FAISS"""
        if self.index.ntotal == 0:
            return []
        qvec = await self.embed_text(query)
        D, I = self.index.search(np.expand_dims(qvec, 0), k)
        results = []
        for i in I[0]:
            if i < len(self.store):
                results.append(self.store[i])
        return results

    async def build_context(self, query: str):
        """Ghép short-term + semantic search"""
        relevant = await self.retrieve(query)
        return self.short_history + [{"role": "system", "content": f"Relevant memory: {relevant}"}]
