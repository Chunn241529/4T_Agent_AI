from aiohttp import ClientSession, TCPConnector
from typing import Optional

class SessionManager:
    _instance: Optional[ClientSession] = None

    @classmethod
    async def get_session(cls) -> ClientSession:
        if cls._instance is None or cls._instance.closed:
            cls._instance = ClientSession(
                connector=TCPConnector(
                    limit=100,  # Maximum number of concurrent connections
                    ttl_dns_cache=300,  # DNS cache TTL in seconds
                    keepalive_timeout=120  # Keep-alive timeout
                )
            )
        return cls._instance

    @classmethod
    async def close_session(cls):
        if cls._instance and not cls._instance.closed:
            await cls._instance.close()
            cls._instance = None
