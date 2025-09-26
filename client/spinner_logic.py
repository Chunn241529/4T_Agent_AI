# spinner_logic.py
# -*- coding: utf-8 -*-
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtStateMachine import QStateMachine, QState
from PySide6.QtGui import QFont

class SpinnerLogic:
    def __init__(self, parent):
        self.parent = parent
        self.state_machine = QStateMachine(parent)
        self.spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.spinner_index = 0
        self.spinner_timer = None
        self.spinner_label = None
        self.text_label = None
        self.overlay = None
        self.setup_states()

    def setup_states(self):
        """Thiết lập state machine cho các trạng thái spinner"""
        idle_state = QState()
        search_state = QState()
        thinking_state = QState()
        responding_state = QState()

        # Transitions sử dụng Signal từ ChatWindow
        idle_state.addTransition(self.parent.toSearch, search_state)
        idle_state.addTransition(self.parent.toThinking, thinking_state)
        search_state.addTransition(self.parent.toThinking, thinking_state)
        search_state.addTransition(self.parent.toResponding, responding_state)
        thinking_state.addTransition(self.parent.toSearch, search_state)
        thinking_state.addTransition(self.parent.toResponding, responding_state)
        responding_state.addTransition(self.parent.toIdle, idle_state)
        responding_state.addTransition(self.parent.toSearch, search_state)
        responding_state.addTransition(self.parent.toThinking, thinking_state)

        # Idle: Không hiển thị spinner
        def enter_idle():
            print("Entered idle state")
            self._hide_spinner()
            self.parent.ui.adjust_window_height()

        idle_state.entered.connect(enter_idle)

        # Search: Hiển thị spinner + "Đang tìm kiếm..."
        def enter_search():
            print("Entered search state")
            self._show_spinner("Đang tìm kiếm...")
            if self.spinner_timer:
                self.spinner_timer.start()
                print("Spinner timer started in search state")

        search_state.entered.connect(enter_search)

        # Thinking: Hiển thị spinner + "Đang suy nghĩ..."
        def enter_thinking():
            print("Entered thinking state")
            self._show_spinner("Đang suy nghĩ...")
            if self.spinner_timer:
                self.spinner_timer.start()
                print("Spinner timer started in thinking state")

        thinking_state.entered.connect(enter_thinking)

        # Responding: Ẩn spinner
        def enter_responding():
            print("Entered responding state")
            self._hide_spinner()
            self.parent.ui.adjust_window_height()

        responding_state.entered.connect(enter_responding)

        self.state_machine.addState(idle_state)
        self.state_machine.addState(search_state)
        self.state_machine.addState(thinking_state)
        self.state_machine.addState(responding_state)
        self.state_machine.setInitialState(idle_state)
        self.state_machine.start()
        print("State machine started")

    def _show_spinner(self, text):
        """Hiển thị overlay spinner với ký tự ASCII"""
        if self.overlay:
            self._hide_spinner()
            print("Existing spinner hidden before showing new one")

        self.parent.ui.scroll_area.setVisible(True)
        scroll_width = max(self.parent.ui.scroll_area.width(), 100)
        scroll_height = max(self.parent.ui.scroll_area.height(), 50)
        print(f"scroll_area set visible, size: {scroll_width}x{scroll_height}")

        self.overlay = QWidget(self.parent.ui.scroll_area)
        self.overlay.setStyleSheet("background: transparent;")
        self.overlay.setGeometry(0, 0, scroll_width, 50)
        self.overlay.raise_()
        print(f"Spinner overlay created, geometry: {self.overlay.geometry().width()}x{self.overlay.geometry().height()}, visible: {self.overlay.isVisible()}")

        self.spinner_label = QLabel(self.spinner_chars[self.spinner_index], self.overlay)
        self.spinner_label.setStyleSheet("color: #61afef; font-size: 16px; font-family: 'Courier New', monospace;")
        self.spinner_label.move(10, 15)
        self.spinner_label.raise_()
        self.spinner_label.show()
        print(f"Spinner label shown with char: {self.spinner_chars[self.spinner_index]}, visible: {self.spinner_label.isVisible()}")

        self.text_label = QLabel(text, self.overlay)
        self.text_label.setStyleSheet("color: #e0e0e0; font-size: 14px;")
        self.text_label.move(30, 15)
        self.text_label.raise_()
        self.text_label.show()
        print(f"Text label shown with text: {text}, visible: {self.text_label.isVisible()}")

        self.spinner_timer = QTimer(self.overlay)
        self.spinner_timer.setInterval(100)
        self.spinner_timer.timeout.connect(self._update_spinner)
        print(f"Spinner timer initialized, active: {self.spinner_timer.isActive()}")

        self.overlay.show()
        self.overlay.raise_()
        print(f"Spinner overlay shown, visible: {self.overlay.isVisible()}")
        self.parent.ui.adjust_window_height()

    def _hide_spinner(self):
        """Ẩn spinner"""
        if self.spinner_timer:
            self.spinner_timer.stop()
            self.spinner_timer.deleteLater()
            self.spinner_timer = None
        if self.spinner_label:
            self.spinner_label.deleteLater()
            self.spinner_label = None
        if self.text_label:
            self.text_label.deleteLater()
            self.text_label = None
        if self.overlay:
            self.overlay.deleteLater()
            self.overlay = None
        print("Spinner hidden and cleaned up")

    def _update_spinner(self):
        """Cập nhật ký tự spinner"""
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
        if self.spinner_label:
            self.spinner_label.setText(self.spinner_chars[self.spinner_index])
            # print(f"Spinner updated to char: {self.spinner_chars[self.spinner_index]}")

    def start_search(self):
        """Trigger chuyển sang trạng thái search"""
        self.parent.toSearch.emit()

    def start_thinking(self):
        """Trigger chuyển sang trạng thái thinking"""
        self.parent.toThinking.emit()

    def start_responding(self):
        """Trigger chuyển sang trạng thái responding"""
        self.parent.toResponding.emit()

    def reset_to_idle(self):
        """Trigger chuyển về trạng thái idle"""
        self.parent.toIdle.emit()
