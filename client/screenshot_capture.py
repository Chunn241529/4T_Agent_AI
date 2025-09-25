# screenshot_capture.py
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QPushButton, QHBoxLayout
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor, QScreen
from PySide6.QtCore import Qt, QRect, QPoint, Signal, QByteArray, QBuffer, QIODevice

class ScreenshotOverlay(QWidget):
    screenshot_captured = Signal(QPixmap)  # Signal phát ra khi có screenshot
    cancelled = Signal()  # Signal phát ra khi hủy bỏ
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.3);")
        
        # Lấy screenshot toàn màn hình
        screen = QApplication.primaryScreen()
        if screen:
            self.full_screenshot = screen.grabWindow(0)
        else:
            self.full_screenshot = QPixmap()
        
        self.start_pos = None
        self.end_pos = None
        self.drawing = False
        self.selection_rect = QRect()
        
        # Tạo preview widget
        self.preview_widget = QWidget()
        self.preview_widget.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.preview_widget.setAttribute(Qt.WA_TranslucentBackground)
        self.preview_widget.setStyleSheet("background-color: rgba(0, 0, 0, 0.8); border-radius: 10px;")
        self.preview_widget.setFixedSize(200, 150)
        
        preview_layout = QVBoxLayout(self.preview_widget)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("color: white; font-size: 12px;")
        preview_layout.addWidget(self.preview_label)
        
        button_layout = QHBoxLayout()
        self.confirm_button = QPushButton("Xác nhận")
        self.cancel_button = QPushButton("Hủy")
        self.confirm_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        self.confirm_button.clicked.connect(self.confirm_selection)
        self.cancel_button.clicked.connect(self.cancel_selection)
        
        button_layout.addWidget(self.confirm_button)
        button_layout.addWidget(self.cancel_button)
        preview_layout.addLayout(button_layout)
        
        self.preview_widget.hide()
    
    def showEvent(self, event):
        super().showEvent(event)
        # Set kích thước full màn hình
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        self.preview_widget.hide()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Vẽ overlay màu xám
        overlay_color = QColor(0, 0, 0, 100)
        painter.fillRect(self.rect(), overlay_color)
        
        # Nếu đang chọn vùng, vẽ vùng chọn
        if not self.selection_rect.isNull():
            # Vẽ vùng chọn với viền trắng
            painter.setPen(QPen(Qt.white, 2))
            painter.setBrush(QColor(255, 255, 255, 30))
            painter.drawRect(self.selection_rect)
            
            # Hiển thị kích thước vùng chọn
            size_text = f"{self.selection_rect.width()} x {self.selection_rect.height()}"
            painter.setPen(Qt.white)
            painter.drawText(self.selection_rect.topLeft() + QPoint(5, -5), size_text)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.drawing = True
            self.selection_rect = QRect()
            self.update()
    
    def mouseMoveEvent(self, event):
        if self.drawing and self.start_pos:
            self.end_pos = event.pos()
            self.selection_rect = QRect(self.start_pos, self.end_pos).normalized()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing:
            self.drawing = False
            if not self.selection_rect.isNull() and self.selection_rect.width() > 10 and self.selection_rect.height() > 10:
                # Hiển thị preview widget
                self.show_preview()
            else:
                self.selection_rect = QRect()
                self.update()
    
    def show_preview(self):
        if not self.selection_rect.isNull():
            # Cắt ảnh từ vùng chọn
            cropped_pixmap = self.full_screenshot.copy(self.selection_rect)
            
            # Scale ảnh để hiển thị trong preview (gi giữ tỷ lệ)
            scaled_pixmap = cropped_pixmap.scaled(180, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            # Hiển thị ảnh trong preview
            self.preview_label.setPixmap(scaled_pixmap)
            self.preview_label.setText("")
            
            # Hiển thị preview widget ở góc dưới bên phải
            screen_geo = QApplication.primaryScreen().geometry()
            preview_x = screen_geo.right() - 220
            preview_y = screen_geo.bottom() - 170
            self.preview_widget.move(preview_x, preview_y)
            self.preview_widget.show()
    
    def confirm_selection(self):
        if not self.selection_rect.isNull():
            # Cắt ảnh từ vùng chọn
            cropped_pixmap = self.full_screenshot.copy(self.selection_rect)
            
            # Ẩn các widget
            self.preview_widget.hide()
            self.hide()
            
            # Phát signal với ảnh đã chụp
            self.screenshot_captured.emit(cropped_pixmap)
        else:
            self.cancel_selection()
    
    def cancel_selection(self):
        self.preview_widget.hide()
        self.hide()
        self.cancelled.emit()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.cancel_selection()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.confirm_selection()
        else:
            super().keyPressEvent(event)

    def pixmap_to_base64(pixmap):
        """Chuyển QPixmap sang base64 string"""
        byte_array = QByteArray()
        buffer = QBuffer(byte_array)
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG")
        return byte_array.toBase64().data().decode()
