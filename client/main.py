# main.py
# -*- coding: utf-8 -*-
import sys
from PySide6.QtWidgets import QApplication
from chat_window import ChatWindow
from tray_icon import TrayIconManager


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    
    chat_window = ChatWindow()
    TrayIconManager(app, chat_window)
    
    print("Ứng dụng đã khởi động. Click vào icon trên khay hệ thống.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
