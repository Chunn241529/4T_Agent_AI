# chat_logic.py
# -*- coding: utf-8 -*-
import markdown
import json
from typing import Optional
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit
from worker import OllamaWorker

class ChatLogic:
    def __init__(self, parent):
        self.parent = parent
        self.ollama_thread: Optional[OllamaWorker] = None
        self.chunk_buffer = ""
        self.buffer_timer = QTimer()
        self.buffer_timer.setInterval(200)  # Buffer mỗi 200ms
        self.buffer_timer.timeout.connect(self._flush_buffer)
        self.parent.user_scrolling = False  # Khởi tạo user_scrolling

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

        if self.ollama_thread:
            self.ollama_thread.deleteLater()
            self.ollama_thread = None

        self.ollama_thread = OllamaWorker(prompt_text)
        self.ollama_thread.chunk_received.connect(self._buffer_chunk)
        self.ollama_thread.search_started.connect(self.on_search_started)
        self.ollama_thread.search_sources.connect(self.on_search_sources)
        self.ollama_thread.content_started.connect(self.on_content_started)
        self.ollama_thread.error_received.connect(self.handle_error)
        self.ollama_thread.finished.connect(self.on_generation_finished)
        self.ollama_thread.start()
        print("OllamaWorker started")

    def _buffer_chunk(self, chunk: str) -> None:
        self.chunk_buffer += chunk
        if not self.buffer_timer.isActive():
            self.buffer_timer.start()
        print(f"Buffered chunk: {chunk[:50]}...")

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
        print(f"Before setHtml: scroll_value={scroll_value}, scroll_max={scroll_max}")

        wrapped_html = f'<div style="padding: 15px 10px;">{html_content}</div>'
        self.parent.ui.response_display.setHtml(wrapped_html)
        print("Response HTML set")

        # Dùng ensureCursorVisible để auto-scroll
        if not self.parent.user_scrolling:
            cursor = self.parent.ui.response_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.parent.ui.response_display.setTextCursor(cursor)
            self.parent.ui.response_display.ensureCursorVisible()
            print(f"Auto-scroll with ensureCursorVisible, cursor at: {cursor.position()}")

        self.chunk_buffer = ""
        self.parent.adjust_window_height()

    def handle_error(self, error_message: str) -> None:
        print(f"Received error: {error_message}")
        self.parent.spinner_logic.reset_to_idle()
        self.parent.full_response_md = error_message
        html_content = markdown.markdown(
            error_message, extensions=['fenced_code', 'tables', 'codehilite']
        )

        wrapped_html = f'<div style="padding: 15px 10px;">{html_content}</div>'
        self.parent.ui.response_display.setHtml(wrapped_html)
        print("Error HTML set")

        if not self.parent.user_scrolling:
            cursor = self.parent.ui.response_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.parent.ui.response_display.setTextCursor(cursor)
            self.parent.ui.response_display.ensureCursorVisible()
            print(f"Auto-scroll with ensureCursorVisible on error, cursor at: {cursor.position()}")

        self._reset_input()

    def on_generation_finished(self) -> None:
        print("Generation finished")
        self.buffer_timer.stop()
        self._flush_buffer()
        self.parent.spinner_logic.reset_to_idle()
        self._reset_input()
        if self.ollama_thread:
            self.ollama_thread.deleteLater()
            self.ollama_thread = None

    def _reset_input(self) -> None:
        self.parent.ui.input_box.setDisabled(False)
        self.parent.ui.input_box.setPlaceholderText("Hỏi 4T...")
        self.parent.ui.input_box.clear()
        self.parent.ui.input_box.setFocus()
        self.parent.adjust_window_height()

    def on_search_started(self) -> None:
        print("on_search_started called")
        self.parent.spinner_logic.start_search()

    def on_content_started(self) -> None:
        print("on_content_started called, triggering thinking state")
        self.parent.spinner_logic.start_thinking()

    def on_search_sources(self, sources_json: str) -> None:
        print(f"Received sources: {sources_json}")
        if not sources_json.strip():
            print("Empty sources JSON, skipping")
            return

        try:
            self.parent.sources_data = json.loads(sources_json)
            if self.parent.sources_data:
                sources_html = (
                    "<div style='padding: 10px; border-left: 3px solid #61afef; "
                    "margin: 10px 0; background: rgba(97, 175, 239, 0.1);'>"
                    "<div style='font-weight: bold; color: #61afef; margin-bottom: 5px;'>"
                    "Tìm kiếm trên web:</div>"
                )
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

    def on_scroll_changed(self, value: int) -> None:
        scroll_bar = self.parent.ui.scroll_area.verticalScrollBar()
        max_value = scroll_bar.maximum()
        scroll_threshold = max(20, self.parent.ui.scroll_area.height() // 4)  # Tăng threshold
        self.parent.user_scrolling = max_value - value > scroll_threshold
        print(f"Scroll changed, user_scrolling: {self.parent.user_scrolling}, value: {value}, max: {max_value}")
        self.parent.last_scroll_value = value