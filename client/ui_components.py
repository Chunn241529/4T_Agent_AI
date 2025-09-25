# ui_components.py
# -*- coding: utf-8 -*-
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QFrame,
    QScrollArea, QTextBrowser, QPushButton, QHBoxLayout, QLabel
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap

class UIComponents:
    def __init__(self, parent):
        self.parent = parent
        self.main_container = None
        self.container_layout = None
        self.main_frame = None
        self.input_box = None
        self.scroll_area = None
        self.response_display = None
        self.button_widget = None
        self.screenshot_button = None
        self.preview_widget = None
        self.icon_label = None
        self.name_label = None
        self.size_label = None

    def setup_ui(self):
        self.parent.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.parent.setAttribute(Qt.WA_TranslucentBackground)
        self.parent.setWindowTitle("4T Assistant")
        self.parent.setFixedWidth(600)
        
        self.parent.layout = QVBoxLayout(self.parent)
        self.parent.layout.setContentsMargins(0, 0, 0, 0)
        
        self.main_container = QWidget()
        self.main_container.setObjectName("mainContainer")
        self.container_layout = QVBoxLayout(self.main_container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(10)
        
        self.main_frame = QFrame(self.main_container)
        self.main_frame.setObjectName("mainFrame")
        frame_layout = QVBoxLayout(self.main_frame)
        frame_layout.setSpacing(10)
        
        self.preview_widget = QWidget(self.main_frame)
        self.preview_widget.setObjectName("previewWidget")
        preview_layout = QHBoxLayout(self.preview_widget)
        preview_layout.setContentsMargins(10, 5, 10, 5)
        preview_layout.setSpacing(10)
        
        self.icon_label = QLabel()
        self.icon_label.setFixedSize(40, 40)
        self.icon_label.setScaledContents(True)
        preview_layout.addWidget(self.icon_label)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        self.name_label = QLabel("Screenshot.png")
        self.name_label.setStyleSheet("color: #e0e0e0; font-size: 12px;")
        self.size_label = QLabel("0x0")
        self.size_label.setStyleSheet("color: #a0a0a0; font-size: 10px;")
        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.size_label)
        preview_layout.addLayout(info_layout)
        
        preview_layout.addStretch()
        frame_layout.addWidget(self.preview_widget)
        self.preview_widget.hide()
        
        self.input_box = QTextEdit(self.main_frame)
        self.input_box.setObjectName("inputBox")
        self.input_box.setPlaceholderText("Hỏi 4T...")
        self.input_box.setFixedHeight(80)
        self.input_box.keyPressEvent = self.parent.handle_key_press
        self.input_box.setAcceptRichText(True)

        self.scroll_area = QScrollArea(self.main_frame)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setObjectName("scrollArea")
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.parent.on_scroll_changed)
        
        self.response_display = QTextBrowser(self.scroll_area)
        self.response_display.setObjectName("responseDisplay")
        self.response_display.setOpenExternalLinks(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setWidget(self.response_display)
        
        frame_layout.addWidget(self.input_box)
        frame_layout.addWidget(self.scroll_area)
        
        self.container_layout.addWidget(self.main_frame)
        
        self.button_widget = QWidget()
        button_layout = QHBoxLayout(self.button_widget)
        button_layout.setContentsMargins(5, 0, 0, 0)
        
        self.screenshot_button = QPushButton("📷", self.parent)
        self.screenshot_button.setObjectName("screenshotButton")
        self.screenshot_button.setFixedSize(60, 30)
        self.screenshot_button.clicked.connect(self.parent.on_screenshot_clicked)
        self.screenshot_button.setCursor(Qt.PointingHandCursor)
        
        button_layout.addWidget(self.screenshot_button)
        button_layout.addStretch()
        
        self.parent.layout.addWidget(self.main_container)
        self.parent.layout.addWidget(self.button_widget)
        
        print("scroll_area initialized, not hidden")
        self.apply_stylesheet()
        self.parent.adjustSize()
        print(f"Initial window size: {self.parent.size().width()}x{self.parent.size().height()}")

    def apply_stylesheet(self):
        self.parent.setStyleSheet("""
            #mainContainer { 
                background-color: transparent;
            }
            #mainFrame { 
                background-color: rgba(28, 29, 35, 0.95); 
                border: 1px solid #505050; 
                border-radius: 20px; 
            }
            #previewWidget {
                background-color: rgba(28, 29, 35, 0.95);
                border: 1px solid #505050;
                border-radius: 9px;
            }
            #previewWidget:hover {
                background-color: #3a3b45;
                border: 1px solid #61afef;
            }
            #inputBox { 
                background-color: #2c2d35; 
                border: 1px solid #505050; 
                border-radius: 10px; 
                color: #e0e0e0; 
                font-size: 14px; 
                padding: 10px; 
            }
            #scrollArea, #scrollArea > QWidget > QWidget { 
                border: none; 
                background: transparent; 
            }
            #responseDisplay { 
                background-color: transparent; 
                color: #e0e0e0; 
                font-size: 14px; 
                border: none; 
            }
            #responseDisplay a { 
                color: #61afef; 
                text-decoration: none; 
            }
            #responseDisplay a:hover { 
                text-decoration: underline; 
            }
            #responseDisplay table { 
                border-collapse: collapse; 
                margin: 1em 0; 
                width: 100%; 
                border: 1px solid #705050; 
            }
            #responseDisplay th, #responseDisplay td { 
                border: 1px solid #705050; 
                padding: 8px; 
                text-align: left; 
            }
            #responseDisplay th { 
                background-color: #3a3b45; 
                color: #e0e0e0; 
                font-weight: bold; 
            }
            #responseDisplay td { 
                background-color: #2c2d35; 
            }
            .codehilite { 
                background: #2c2d35; 
                border-radius: 5px; 
                padding: 10px; 
                font-size: 13px; 
                margin: 1em 0; 
            }
            .codehilite pre { 
                margin: 0; 
                white-space: pre-wrap; 
            }
            .codehilite .k { 
                color: #c678dd; 
            } 
            .codehilite .s2 { 
                color: #98c379; 
            }
            .codehilite .nf { 
                color: #61afef; 
            } 
            .codehilite .mi { 
                color: #d19a66; 
            }
            .codehilite .n { 
                color: #abb2bf; 
            } 
            .codehilite .p { 
                color: #abb2bf; 
            }
            .codehilite .o { 
                color: #56b6c2; 
            } 
            .codehilite .nb { 
                color: #d19a66; 
            }
            .codehilite .c1 { 
                color: #7f848e; 
                font-style: italic; 
            }
            #screenshotButton {
                background-color: rgba(28, 29, 35, 0.95);
                border: 1px solid #505050;
                border-radius: 9px;
                color: #e0e0e0;
                font-size: 14px;
                padding: 0px;
                text-align: center;
            }
            #screenshotButton:hover {
                background-color: #3a3b45;
                border: 1px solid #61afef;
            }
            #screenshotButton:pressed {
                background-color: #1a1b25;
            }
            QScrollBar:vertical { 
                width: 0px; 
            }
        """)

    def mouse_press_event(self, event):
        if event.button() == Qt.RightButton:
            self.parent.dragging = True
            self.parent.drag_position = event.globalPosition().toPoint() - self.parent.pos()
            event.accept()

    def mouse_move_event(self, event):
        if self.parent.dragging and event.buttons() & Qt.RightButton:
            self.parent.move(event.globalPosition().toPoint() - self.parent.drag_position)
            event.accept()

    def mouse_release_event(self, event):
        if event.button() == Qt.RightButton:
            self.parent.dragging = False
            event.accept()
    
    def adjust_window_height(self):
        doc_height = self.response_display.document().size().toSize().height()
        input_height = self.input_box.height()
        preview_height = self.preview_widget.sizeHint().height() if self.preview_widget.isVisible() else 0
        button_height = self.button_widget.sizeHint().height()
        
        container_margins = self.container_layout.contentsMargins()
        container_margin = container_margins.top() + container_margins.bottom()
        
        frame_margins = self.main_frame.layout().contentsMargins()
        frame_margin = frame_margins.top() + frame_margins.bottom()
        
        spacing = self.main_frame.layout().spacing()
        
        response_padding = 20
        
        target_height = input_height + doc_height + preview_height + button_height + container_margin + frame_margin + spacing * 2 + response_padding

        final_height = min(target_height, self.parent.MAX_HEIGHT)
        
        if self.parent.height() != final_height:
            self.parent.setFixedHeight(final_height)
            print(f"Adjusted window height to: {final_height}, preview_height: {preview_height}")