# app/services/memory_manager.py
from app.utils.logger import logger
import faiss
import numpy as np
from datetime import datetime
from app.services.session_manager import SessionManager
from app.utils.embed import embed_text  # Import hàm chung

class HybridMemory:
    def __init__(self, dim=1024, max_short=20):
        self.short_history = []
        self.max_short = max_short
        self.index = faiss.IndexFlatL2(dim)  # FAISS vector store
        self.store = []  # metadata song song với FAISS

    async def add_message(self, role: str, content: str):
        """Lưu message vào short-term, nếu tràn thì đẩy vào FAISS"""
        self.short_history.append({"role": role, "content": content})
        if len(self.short_history) > self.max_short:
            old = self.short_history.pop(0)
            vec = await embed_text(old["content"])  # Dùng hàm chung
            if vec is not None:
                self.index.add(np.expand_dims(vec, 0))
                self.store.append({"role": old["role"], "content": old["content"], "time": datetime.utcnow()})
            else:
                logger.warning("Bỏ qua embed cho old message do lỗi")

    async def retrieve(self, query: str, k=5):
        """Semantic search từ FAISS"""
        if self.index.ntotal == 0:
            return []
        qvec = await embed_text(query)  # Dùng hàm chung
        if qvec is None:
            return []
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
