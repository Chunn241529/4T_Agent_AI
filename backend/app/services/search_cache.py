# app/services/search_cache.py
from typing import Dict, List, Optional
from datetime import datetime, timedelta

class SearchCache:
    def __init__(self, ttl_minutes: int = 30):
        self._cache: Dict[str, Dict] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    def get(self, query: str) -> Optional[List[dict]]:
        """Lấy kết quả từ cache nếu có và chưa hết hạn"""
        if query in self._cache:
            cache_entry = self._cache[query]
            if datetime.now() - cache_entry['timestamp'] < self._ttl:
                return cache_entry['results']
            # Xóa cache đã hết hạn
            del self._cache[query]
        return None

    def set(self, query: str, results: List[dict]) -> None:
        """Lưu kết quả tìm kiếm vào cache"""
        self._cache[query] = {
            'results': results,
            'timestamp': datetime.now()
        }

    def cleanup(self) -> None:
        """Xóa các cache đã hết hạn"""
        now = datetime.now()
        expired = [k for k, v in self._cache.items()
                  if now - v['timestamp'] > self._ttl]
        for k in expired:
            del self._cache[k]

# Khởi tạo singleton instance
search_cache = SearchCache()
