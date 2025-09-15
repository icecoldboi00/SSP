# --- START OF FILE idle_screen.py ---

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QSpacerItem, QSizePolicy, QDialog, QStackedLayout, QGraphicsDropShadowEffect)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap, QColor

from screens.pin_dialog import PinDialog

def get_base_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class IdleScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.setup_ui()
    
    def setup_ui(self):
        # --- THEME COLORS ---
        COLOR_BACKGROUND = "#FFFFFF"
        COLOR_PRIMARY_GREEN = "#006837"
        COLOR_LIGHT_GRAY_TEXT = "#666666"

        main_layout = QStackedLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setStackingMode(QStackedLayout.StackAll)
        
        background_label = QLabel()
        background_label.setStyleSheet(f"background-color: {COLOR_BACKGROUND};")

        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'idle_screen background.png')

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            background_label.setPixmap(pixmap)
            background_label.setScaledContents(True) 
            background_label.setAlignment(Qt.AlignCenter)
        else:
            print(f"WARNING: Background image not found at '{image_path}'.")

        foreground_frame = QFrame()
        foreground_frame.setStyleSheet("background-color: transparent;")
        
        frame_layout = QVBoxLayout(foreground_frame)
        frame_layout.setContentsMargins(50, 50, 50, 30)
        frame_layout.setSpacing(10)
        
        # --- "Touch to Start" Label ---
        touch_to_start_label = QLabel("TOUCH SCREEN TO START")
        touch_to_start_label.setAlignment(Qt.AlignCenter)
        touch_to_start_label.setStyleSheet("color: #36454F; font-size: 52px; font-weight: bold; padding: 20px;")
        
        # --- Supported Formats Label ---
        bottom_info = QLabel("Supported Format: PDF Files Only")
        bottom_info.setAlignment(Qt.AlignCenter)
        bottom_info.setStyleSheet("color: #36454F; font-size: 16px;")

        # --- MODIFICATION: The drop shadow effect code has been removed. ---
        
        # --- Layout Adjustments for Centering ---
        frame_layout.addStretch(2) 
        frame_layout.addWidget(touch_to_start_label)
        frame_layout.addWidget(bottom_info)
        frame_layout.addStretch(2) 
        
        # --- Admin Button ---
        admin_button = QPushButton("Admin")
        admin_button.setFixedSize(90, 35)
        admin_button.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: {COLOR_BACKGROUND};"
            f"  color: {COLOR_LIGHT_GRAY_TEXT};"
            f"  font-size: 13px;"
            f"  border: 1px solid #CCCCCC;"
            f"  border-radius: 8px;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: #f0f0f0;"
            f"  color: {COLOR_PRIMARY_GREEN};"
            f"  border-color: {COLOR_PRIMARY_GREEN};"
            f"}}"
        )
        admin_button.clicked.connect(self.go_to_admin)
        
        admin_layout = QHBoxLayout()
        admin_layout.addStretch(1)
        admin_layout.addWidget(admin_button)
        frame_layout.addLayout(admin_layout)

        main_layout.addWidget(background_label)
        main_layout.addWidget(foreground_frame)
        
        self.setLayout(main_layout)
    
    def mousePressEvent(self, event):
        admin_button = self.findChild(QPushButton)
        if not admin_button or not admin_button.geometry().contains(event.pos()):
            self.start_printing()

    def start_printing(self):
        self.main_app.show_screen('usb')

    def go_to_admin(self):
        dialog = PinDialog(self)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            self.main_app.show_screen('admin')
        else:
            print("PIN Dialog closed without correct PIN.")
    
    def on_enter(self): pass
    def on_leave(self): pass