# chat_window.py
# -*- coding: utf-8 -*-
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import Qt, QPoint, Signal
from ui_components import UIComponents
from chat_logic import ChatLogic
from spinner_logic import SpinnerLogic

class ChatWindow(QWidget):
    MAX_HEIGHT = 500
    # Định nghĩa các tín hiệu cho QStateMachine
    toSearch = Signal()
    toThinking = Signal()
    toResponding = Signal()
    toIdle = Signal()

    def __init__(self):
        super().__init__()
        self._is_stable = False
        self.full_response_md = ""
        self.dragging = False
        self.drag_position = QPoint()
        self.waiting_for_response = False
        self.user_scrolling = False
        self.last_scroll_value = 0
        self.sources_data = []
        
        self.ui = UIComponents(self)
        self.chat_logic = ChatLogic(self)
        self.spinner_logic = SpinnerLogic(self)
        
        self.init_ui()

    def init_ui(self):
        self.ui.setup_ui()
        self.chat_logic.setup_connections()

    def focusInEvent(self, event):
        self._is_stable = True
        super().focusInEvent(event)

    def showEvent(self, event):
        self._is_stable = False
        super().showEvent(event)
        self.ui.input_box.setFocus()

    def focusOutEvent(self, event):
        if self._is_stable:
            self.hide()
        super().focusOutEvent(event)
    
    def mousePressEvent(self, event):
        self.ui.mouse_press_event(event)

    def mouseMoveEvent(self, event):
        self.ui.mouse_move_event(event)

    def mouseReleaseEvent(self, event):
        self.ui.mouse_release_event(event)

    def handle_key_press(self, event):
        self.chat_logic.handle_key_press(event)

    def send_prompt(self):
        self.chat_logic.send_prompt()

    def update_response(self, chunk):
        self.chat_logic.update_response(chunk)

    def handle_error(self, error_message):
        self.chat_logic.handle_error(error_message)

    def on_generation_finished(self):
        self.chat_logic.on_generation_finished()

    def on_search_started(self):
        self.chat_logic.on_search_started()

    def on_search_sources(self, sources_json):
        self.chat_logic.on_search_sources(sources_json)

    def on_scroll_changed(self, value):
        self.chat_logic.on_scroll_changed(value)

    def on_screenshot_clicked(self):
        self.chat_logic.on_screenshot_clicked()

    def adjust_window_height(self):
        self.ui.adjust_window_height()

    def apply_stylesheet(self):
        self.ui.apply_stylesheet()