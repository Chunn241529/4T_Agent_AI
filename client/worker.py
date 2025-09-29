# worker.py
# -*- coding: utf-8 -*-
from asyncio.log import logger
import json
import base64
import gc
from PySide6.QtCore import QThread, Signal
import aiohttp
import asyncio
import re

class OllamaWorker(QThread):
    chunk_received = Signal(str)
    thinking_received = Signal(str)
    search_started = Signal(str)
    search_sources = Signal(str)
    content_started = Signal()
    image_processing = Signal()
    image_description = Signal(str)
    error_received = Signal(str)
    finished = Signal()

    def __init__(self, prompt: str, image_base64: str = None, is_thinking: bool = False):
        super().__init__()
        self.prompt = prompt
        self.image_base64 = image_base64
        self.is_thinking = is_thinking
        self.base_url = "http://localhost:8000"
        self.max_image_size = 20 * 1024 * 1024
        self.partial_buffer = ""
        self.thinking_buffer = ""
        self.in_thinking = False
        self._cancelled = False
        self._session = None
        self._task = None

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._task = loop.create_task(self._stream_response())
            loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            print("Stream response cancelled")
        except Exception as e:
            self.error_received.emit(f"Lỗi trong OllamaWorker: {str(e)}")
            print(f"OllamaWorker error: {str(e)}")
        finally:
            loop.close()
            self.finished.emit()

    def stop(self):
        self._cancelled = True
        if self._task:
            self._task.cancel()
        if self._session:
            asyncio.create_task(self._session.close())

    async def _stream_response(self):
        try:
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

            self._session = aiohttp.ClientSession()
            payload = {
                "prompt": self.prompt
            }
            if cleaned_image_base64:
                payload["image"] = cleaned_image_base64
            logger.debug(f"Gửi payload: {json.dumps(payload, ensure_ascii=False)[:100]}...")

            async with self._session.post(
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:
                if response.status != 200:
                    self.error_received.emit(f"Lỗi HTTP: {response.status}")
                    print(f"HTTP error: {response.status}")
                    return

                async for line in response.content:
                    if self._cancelled:
                        raise asyncio.CancelledError("Stream cancelled by user")

                    if not line.strip():
                        logger.debug("Bỏ qua dòng rỗng từ server")
                        continue
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if data.get("type") == "search_start":
                            self.search_started.emit(data.get("query", ""))
                        elif data.get("type") == "sources":
                            sources_str = json.dumps(data.get("sources", []), separators=(',', ':')).replace('\n', '')
                            if len(sources_str) > 20:
                                sources_str = sources_str[:20] + "..."
                            self.search_sources.emit(sources_str)
                        elif data.get("type") == "content_start":
                            self.content_started.emit()
                        elif data.get("type") == "image_processing":
                            self.image_processing.emit()
                        elif data.get("type") == "image_description":
                            self.image_description.emit(data["content"])
                        elif data.get("type") == "error":
                            self.error_received.emit(data["message"]["content"])
                        elif "message" in data:
                            message = data["message"]
                            if "thinking" in message:
                                thinking = message["thinking"]
                                if thinking and isinstance(thinking, str):
                                    self.thinking_received.emit(thinking)
                            if "content" in message:
                                content = message["content"]
                                if content and isinstance(content, str):
                                    content = content.replace('\\u003c', '<').replace('\\u003e', '>')
                                    content = self.partial_buffer + content
                                    self.partial_buffer = ""

                                    if not self.in_thinking:
                                        think_start = content.find('<think>')
                                        if think_start == -1:
                                            if content:
                                                self.chunk_received.emit(content)
                                        else:
                                            before = content[:think_start]
                                            if before:
                                                self.chunk_received.emit(before)
                                            content = content[think_start + len('<think>'):]
                                            self.in_thinking = True
                                            self.thinking_buffer += content
                                            if self.thinking_buffer:
                                                self.thinking_received.emit(self.thinking_buffer)
                                                self.thinking_buffer = ""
                                    else:
                                        think_end = content.find('</think>')
                                        if think_end == -1:
                                            self.thinking_buffer += content
                                            if self.thinking_buffer:
                                                self.thinking_received.emit(self.thinking_buffer)
                                                self.thinking_buffer = ""
                                        else:
                                            thinking_part = content[:think_end]
                                            if thinking_part:
                                                self.thinking_buffer += thinking_part
                                                self.thinking_received.emit(self.thinking_buffer)
                                                self.thinking_buffer = ""
                                            after = content[think_end + len('</think>'):]
                                            if after:
                                                self.chunk_received.emit(after)
                                            self.in_thinking = False

                                    if content and (content.endswith('<think') or content.endswith('</think') or content.endswith('<')):
                                        self.partial_buffer = content
                    except json.JSONDecodeError as e:
                        logger.error(f"Lỗi giải mã JSON: {e}, Raw line: {line.decode('utf-8')[:100]}")
                        self.error_received.emit(f"Dữ liệu không hợp lệ từ server: {line.decode('utf-8')[:100]}")
                        continue
                    finally:
                        gc.collect()
        except asyncio.CancelledError:
            print("Stream response cancelled")
            raise
        except Exception as e:
            self.error_received.emit(f"Lỗi kết nối server: {str(e)}")
            print(f"Server connection error: {str(e)}")
        finally:
            if self._session:
                await self._session.close()
                self._session = None
            if self.thinking_buffer:
                self.thinking_received.emit(self.thinking_buffer)
                self.thinking_buffer = ""
            if self.partial_buffer:
                self.chunk_received.emit(self.partial_buffer)
                self.partial_buffer = ""
            gc.collect()
            self.finished.emit()
