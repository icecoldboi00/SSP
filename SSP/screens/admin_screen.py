# --- START OF FILE admin_screen.py ---

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt

class AdminScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background-color: #1f1f38;")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        title = QLabel("Admin Panel")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 36px;
                font-weight: bold;
            }
        """)
        
        # You can add admin-specific widgets here in the future
        placeholder_label = QLabel("Admin controls and settings will be here.")
        placeholder_label.setAlignment(Qt.AlignCenter)
        placeholder_label.setStyleSheet("color: #cccccc; font-size: 16px;")

        back_button = QPushButton("← Back to Main Screen")
        back_button.setMinimumHeight(50)
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #804d4d;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #905d5d;
            }
        """)
        back_button.clicked.connect(self.go_back)
        
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(placeholder_label)
        layout.addStretch(2)
        layout.addWidget(back_button)
        
        self.setLayout(layout)
        
    def go_back(self):
        """Navigate back to the idle screen"""
        self.main_app.show_screen('idle')

    def on_enter(self):
        """Called when this screen becomes active."""
        print("DEBUG: Admin screen entered.")
        
    def on_leave(self):
        """Called when this screen is left."""
        print("DEBUG: Admin screen left.")