# main.py
# -*- coding: utf-8 -*-
import sys
import os
import shutil
import gc
from PySide6.QtWidgets import QApplication, QSplashScreen, QLabel, QMessageBox
from PySide6.QtGui import QPixmap, QPainter, QFont, QColor, Qt
from PySide6.QtCore import Qt as QtCore
from chat_window import ChatWindow
from tray_icon import TrayIconManager
import torch  # Để clean GPU nếu có

def clear_python_cache():
    """Xóa các thư mục __pycache__ trong sys.path"""
    for path in sys.path:
        cache_dir = os.path.join(path, '__pycache__')
        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir, ignore_errors=True)
            print(f"Đã xóa cache tại: {cache_dir}")

def clean_resources():
    """Clean RAM và GPU"""
    gc.collect()
    print("Đã clean RAM (garbage collection)")
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        print("Đã clean GPU cache")

def create_4t_pixmap(width, height):
    """Tạo pixmap với chữ 4T"""
    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    font = QFont("Arial", 120, QFont.Bold)
    painter.setFont(font)
    painter.setPen(QColor("white"))
    text_rect = painter.fontMetrics().boundingRect("4T")
    text_x = (pixmap.width() - text_rect.width()) // 2
    text_y = (pixmap.height() - text_rect.height()) // 2
    painter.drawText(text_x, text_y + painter.fontMetrics().ascent(), "4T")
    painter.end()
    return pixmap

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # Tạo pixmap cho splash với chữ 4T lớn ở giữa
    splash_pixmap = create_4t_pixmap(400, 300)
    splash = QSplashScreen(splash_pixmap, QtCore.WindowStaysOnTopHint)
    splash.setWindowFlags(QtCore.FramelessWindowHint | QtCore.WindowStaysOnTopHint)

    # Tạo label cho message và căn giữa
    message_label = QLabel("Khởi động 4T Assistant...", splash)
    message_label.setAlignment(QtCore.AlignCenter)
    message_label.setStyleSheet("color: white; font-size: 14px; background: transparent;")
    splash.show()
    # Căn giữa label
    splash_size = splash.size()
    label_size = message_label.sizeHint()
    message_label.move((splash_size.width() - label_size.width()) // 2, splash_size.height() - 50)
    app.processEvents()

    # Clean resources
    # message_label.setText("Kiểm tra tài nguyên...")
    # Cập nhật vị trí label sau khi text thay đổi
    label_size = message_label.sizeHint()
    message_label.move((splash_size.width() - label_size.width()) // 2, splash_size.height() - 50)
    app.processEvents()
    clear_python_cache()
    clean_resources()

    chat_window = ChatWindow()
    TrayIconManager(app, chat_window)

    # Ẩn splash
    splash.finish(chat_window)

    # Hiển thị thông báo với icon 4T
    msg_box = QMessageBox()
    msg_box.setWindowTitle("4T Assistant")
    msg_box.setText("Ứng dụng 4T Assistant đã khởi động thành công.\nĐang chạy ở chế độ nền trong khay hệ thống.")
    # msg_box.setIconPixmap(create_4t_pixmap(64, 64))  # Icon nhỏ cho QMessageBox
    msg_box.setStandardButtons(QMessageBox.Ok)
    msg_box.exec()

    print("Ứng dụng đã khởi động. Click vào icon trên khay hệ thống.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
