# worker.py
# -*- coding: utf-8 -*-
import json
from PySide6.QtCore import QThread, Signal
import aiohttp
import asyncio

class OllamaWorker(QThread):
    chunk_received = Signal(str)
    search_started = Signal()
    search_sources = Signal(str)
    content_started = Signal()
    error_received = Signal(str)
    finished = Signal()

    def __init__(self, prompt: str):
        super().__init__()
        self.prompt = prompt
        self.base_url = "http://localhost:8000"  # URL của FastAPI server

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._stream_response())
            loop.close()
        except Exception as e:
            self.error_received.emit(f"Lỗi trong OllamaWorker: {str(e)}")
            print(f"OllamaWorker error: {str(e)}")

    async def _stream_response(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json={"prompt": self.prompt, "model": "gemma3:4b"}
                ) as response:
                    if response.status != 200:
                        self.error_received.emit(f"Lỗi HTTP: {response.status}")
                        print(f"HTTP error: {response.status}")
                        return

                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                # print(f"Received data: {data}")  # Debug log
                                if data.get("type") == "search_start":
                                    self.search_started.emit()
                                    # print("Emitted search_started")
                                elif data.get("type") == "sources":
                                    self.search_sources.emit(json.dumps(data.get("sources", [])))
                                    # print(f"Emitted search_sources: {data.get('sources')}")
                                elif data.get("type") == "content_start":
                                    self.content_started.emit()
                                    # print("Emitted content_started")
                                elif data.get("type") == "content":
                                    self.chunk_received.emit(data["message"]["content"])
                                    # print(f"Emitted chunk: {data['message']['content'][:50]}...")
                                elif data.get("type") == "error":
                                    self.error_received.emit(data["message"]["content"])
                                    # print(f"Emitted error: {data['message']['content']}")
                            except json.JSONDecodeError as e:
                                self.error_received.emit(f"Lỗi giải mã JSON: {str(e)}")
                                print(f"JSON decode error: {str(e)}")
        except Exception as e:
            self.error_received.emit(f"Lỗi kết nối server: {str(e)}")
            print(f"Server connection error: {str(e)}")
        finally:
            self.finished.emit()
            print("Emitted finished")