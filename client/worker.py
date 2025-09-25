# worker.py
# -*- coding: utf-8 -*-
import json
import base64
import gc
from PySide6.QtCore import QThread, Signal
import aiohttp
import asyncio

class OllamaWorker(QThread):
    chunk_received = Signal(str)
    search_started = Signal()
    search_sources = Signal(str)
    content_started = Signal()
    image_processing = Signal()
    image_description = Signal(str)
    error_received = Signal(str)
    finished = Signal()

    def __init__(self, prompt: str, image_base64: str = None):
        super().__init__()
        self.prompt = prompt
        self.image_base64 = image_base64
        self.base_url = "http://localhost:8000"
        self.max_image_size = 20 * 1024 * 1024  # 20MB giới hạn

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._stream_response())
        except Exception as e:
            self.error_received.emit(f"Lỗi trong OllamaWorker: {str(e)}")
            print(f"OllamaWorker error: {str(e)}")
        finally:
            loop.close()
            self.finished.emit()

    async def _stream_response(self):
        try:
            # Kiểm tra và làm sạch base64 nếu có
            cleaned_image_base64 = None
            if self.image_base64:
                try:
                    cleaned_image_base64 = self.image_base64
                    if cleaned_image_base64.startswith('data:image'):
                        cleaned_image_base64 = cleaned_image_base64.split(',')[1]
                    image_size = len(base64.b64decode(cleaned_image_base64))
                    if image_size > self.max_image_size:
                        self.error_received.emit("Hình ảnh quá lớn, vượt quá giới hạn 20MB")
                        print("Image size exceeds 20MB limit")
                        return
                except base64.binascii.Error:
                    self.error_received.emit("Lỗi: Chuỗi base64 không hợp lệ")
                    print("Invalid base64 string")
                    return

            async with aiohttp.ClientSession() as session:
                # Sử dụng gemma3:4b thống nhất
                payload = {"prompt": self.prompt, "model": "gemma3:4b"}
                if cleaned_image_base64:
                    payload["image"] = cleaned_image_base64
                
                async with session.post(
                    f"{self.base_url}/api/chat",
                    json=payload
                ) as response:
                    if response.status != 200:
                        self.error_received.emit(f"Lỗi HTTP: {response.status}")
                        print(f"HTTP error: {response.status}")
                        return

                    async for line in response.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                if data.get("type") == "search_start":
                                    self.search_started.emit()
                                elif data.get("type") == "sources":
                                    self.search_sources.emit(json.dumps(data.get("sources", [])))
                                elif data.get("type") == "content_start":
                                    self.content_started.emit()
                                elif data.get("type") == "content":
                                    self.chunk_received.emit(data["message"]["content"])
                                elif data.get("type") == "error":
                                    self.error_received.emit(data["message"]["content"])
                                elif data.get("type") == "image_processing":
                                    self.image_processing.emit()
                                elif data.get("type") == "image_description":
                                    self.image_description.emit(data["content"])
                            except json.JSONDecodeError as e:
                                self.error_received.emit(f"Lỗi giải mã JSON: {str(e)}")
                                print(f"JSON decode error: {str(e)}")
                            finally:
                                gc.collect()  # Cleanup sau mỗi chunk
        except Exception as e:
            self.error_received.emit(f"Lỗi kết nối server: {str(e)}")
            print(f"Server connection error: {str(e)}")
        finally:
            gc.collect()  # Cleanup cuối cùng
            self.finished.emit()