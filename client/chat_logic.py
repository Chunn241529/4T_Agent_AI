# chat_logic.py
# -*- coding: utf-8 -*-
import markdown
import json
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit
from worker import OllamaWorker
from screenshot_capture import ScreenshotOverlay
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
import re

class ChatLogic:
    def __init__(self, parent):
        self.parent = parent
        self.ollama_thread: Optional[OllamaWorker] = None
        self.chunk_buffer = ""
        self.buffer_timer = QTimer()
        self.buffer_timer.setInterval(50)
        self.buffer_timer.timeout.connect(self._flush_buffer)
        self.parent.user_scrolling = False

    def setup_connections(self) -> None:
        pass

    def handle_key_press(self, event) -> None:
        if event.key() == Qt.Key_Return and not event.modifiers() & Qt.ShiftModifier:
            event.accept()
            if self.ollama_thread and self.ollama_thread.isRunning():
                print("Worker is running, ignoring new prompt")
                return
            self.send_prompt()
        else:
            QTextEdit.keyPressEvent(self.parent.ui.input_box, event)

    def send_prompt(self) -> None:
        prompt_text = self.parent.ui.input_box.toPlainText().strip()
        if not prompt_text:
            print("Prompt is empty, ignoring")
            return

        print(f"Sending prompt: {prompt_text}")
        self.parent.ui.scroll_area.setVisible(True)
        self.parent.ui.input_box.setDisabled(True)
        self.parent.full_response_md = ""
        self.chunk_buffer = ""
        self.parent.ui.response_display.clear()
        self.parent.ui.input_box.setPlaceholderText("AI đang suy nghĩ...")
        self.parent.user_scrolling = False
        self.parent.sources_data = []
        self.parent.waiting_for_response = True
        self.parent.spinner_logic.start_thinking()  # Bắt đầu với trạng thái thinking

        image_base64 = self.parent.current_screenshot_base64

        if self.ollama_thread:
            if self.ollama_thread.isRunning():
                print("Waiting for previous thread to finish")
                self.ollama_thread.quit()
                self.ollama_thread.wait()
            self.ollama_thread.deleteLater()
            self.ollama_thread = None

        self.ollama_thread = OllamaWorker(prompt_text, image_base64=image_base64)
        self.ollama_thread.chunk_received.connect(self._buffer_chunk)
        self.ollama_thread.search_started.connect(self.on_search_started)
        self.ollama_thread.search_sources.connect(self.on_search_sources)
        self.ollama_thread.content_started.connect(self.on_content_started)
        self.ollama_thread.image_processing.connect(self.on_image_processing)
        self.ollama_thread.image_description.connect(self.on_image_description)
        self.ollama_thread.error_received.connect(self.handle_error)
        self.ollama_thread.finished.connect(self.on_generation_finished)
        self.ollama_thread.start()
        print("OllamaWorker started")

    def extract_image_from_input(self):
        return None

    def _buffer_chunk(self, chunk: str) -> None:
        self.chunk_buffer += chunk
        if not self.buffer_timer.isActive():
            self.buffer_timer.start()
        # print(f"Buffered chunk: {chunk[:50]}...")

    def _flush_buffer(self) -> None:
        if not self.chunk_buffer:
            return

        self.parent.spinner_logic.start_responding()
        self.parent.full_response_md += self.chunk_buffer
        html_content = markdown.markdown(
            self.parent.full_response_md, extensions=['fenced_code', 'tables', 'codehilite']
        )

        scroll_bar = self.parent.ui.scroll_area.verticalScrollBar()
        scroll_value = scroll_bar.value()
        scroll_max = scroll_bar.maximum()
        # print(f"Before setHtml: scroll_value={scroll_value}, scroll_max={scroll_max}")

        wrapped_html = f'<div style="padding: 15px 10px;">{html_content}</div>'
        self.parent.ui.response_display.setHtml(wrapped_html)
        # print("Response HTML set")

        if not self.parent.user_scrolling and self.parent.full_response_md:
            cursor = self.parent.ui.response_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.parent.ui.response_display.setTextCursor(cursor)
            self.parent.ui.response_display.ensureCursorVisible()
            print(f"Auto-scroll with ensureCursorVisible, cursor at: {cursor.position()}")

        self.chunk_buffer = ""

    def on_search_started(self):
        self.parent.spinner_logic.start_search()

    def on_search_sources(self, sources_json: str):
        try:
            self.parent.sources_data = json.loads(sources_json)
            sources_html = '<div style="padding: 10px; font-size: 12px; color: #a0a0a0;">'
            for source in self.parent.sources_data:
                sources_html += (
                    f"<div style='margin: 3px 0; font-size: 12px;'>"
                    f"<a href='{source['url']}' style='color: #e0e0e0; text-decoration: none;'>"
                    f"• {source['title']}</a></div>"
                )
            sources_html += "</div>"

            current_html = self.parent.ui.response_display.toHtml()
            body_start = current_html.find("<body>")
            body_end = current_html.find("</body>")
            if body_start != -1 and body_end != -1:
                body_content = current_html[body_start + 6:body_end]
                new_html = current_html[:body_start + 6] + sources_html + body_content + current_html[body_end:]
                self.parent.ui.response_display.setHtml(new_html)
                print("Sources HTML appended")
                if not self.parent.user_scrolling:
                    cursor = self.parent.ui.response_display.textCursor()
                    cursor.movePosition(QTextCursor.End)
                    self.parent.ui.response_display.setTextCursor(cursor)
                    self.parent.ui.response_display.ensureCursorVisible()
                    print(f"Auto-scroll with ensureCursorVisible after sources, cursor at: {cursor.position()}")
            else:
                print("Could not find <body> tags in current HTML")
        except json.JSONDecodeError as e:
            print(f"Error parsing sources JSON: {e}")
        except Exception as e:
            print(f"Error processing sources: {e}")

    def on_content_started(self):
        self.parent.spinner_logic.start_thinking()  # Quay lại thinking khi bắt đầu nội dung

    def on_image_processing(self):
        self.parent.spinner_logic.start_thinking()  # Thinking khi xử lý ảnh

    def on_image_description(self, description: str):
        self.parent.spinner_logic.start_thinking()  # Thinking khi nhận mô tả ảnh

    def on_scroll_changed(self, value: int) -> None:
        scroll_bar = self.parent.ui.scroll_area.verticalScrollBar()
        max_value = scroll_bar.maximum()
        scroll_threshold = max(20, self.parent.ui.scroll_area.height() // 4)
        self.parent.user_scrolling = max_value - value > scroll_threshold
        print(f"Scroll changed, user_scrolling: {self.parent.user_scrolling}, value: {value}, max: {max_value}")
        self.parent.last_scroll_value = value

    def on_screenshot_clicked(self):
        print("Bắt đầu chụp hình")
        self.parent.hide()
        self.screenshot_overlay = ScreenshotOverlay()
        self.screenshot_overlay.screenshot_captured.connect(self.on_screenshot_captured)
        self.screenshot_overlay.cancelled.connect(self.on_screenshot_cancelled)
        self.screenshot_overlay.show()

    def on_screenshot_captured(self, pixmap):
        print("Screenshot đã được chụp")
        self.parent.show()
        self.parent.raise_()
        self.parent.activateWindow()
        self.parent.show_screenshot_preview(pixmap)

    def on_screenshot_cancelled(self):
        print("Chụp hình bị hủy")
        self.parent.show()
        self.parent.raise_()
        self.parent.activateWindow()

    def handle_error(self, error_message):
        self.parent.ui.input_box.setEnabled(True)
        self.parent.ui.input_box.setPlaceholderText("Hỏi 4T...")
        self.parent.waiting_for_response = False
        self.parent.spinner_logic.stop()  # Dừng spinner
        self.parent.ui.response_display.setHtml(f'<div style="padding: 15px 10px; color: #f44336;">{error_message}</div>')
        if self.ollama_thread:
            if self.ollama_thread.isRunning():
                self.ollama_thread.quit()
                self.ollama_thread.wait()
            self.ollama_thread.deleteLater()
            self.ollama_thread = None

    def on_generation_finished(self):
        print("Generation finished")
        self.parent.ui.input_box.setEnabled(True)
        self.parent.ui.input_box.setPlaceholderText("Hỏi 4T...")
        self.parent.ui.input_box.clear()
        self.parent.waiting_for_response = False
        self.parent.spinner_logic.reset_to_idle()  # Chuyển về idle khi hoàn tất
        self.parent.adjust_window_height()
        if self.ollama_thread:
            if self.ollama_thread.isRunning():
                self.ollama_thread.quit()
                self.ollama_thread.wait()
            self.ollama_thread.deleteLater()
            self.ollama_thread = None
