import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QStackedLayout, QHBoxLayout
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

def get_base_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

class ThankYouScreenView(QWidget):
    admin_override_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        stacked_layout = QStackedLayout()
        stacked_layout.setContentsMargins(0, 0, 0, 0)
        stacked_layout.setStackingMode(QStackedLayout.StackAll)

        # --- Background ---
        self.background_label = QLabel()
        self._load_background_image()

        # --- Foreground ---
        foreground_widget = QWidget()
        foreground_widget.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(foreground_widget)
        main_layout.setContentsMargins(50, 50, 50, 50)
        main_layout.setAlignment(Qt.AlignCenter)

        self.status_label = QLabel("Thank you for printing with us")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #36454F; font-size: 56px; font-weight: bold;")

        self.subtitle_label = QLabel("You may now remove your USB")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("color: #36454F; font-size: 32px;")

        # --- Admin Override Button (Hidden by default, shown for errors) ---
        self.admin_override_button = QPushButton("Admin Override")
        self.admin_override_button.setMinimumHeight(45)
        self.admin_override_button.setStyleSheet(self.get_admin_button_style())
        self.admin_override_button.clicked.connect(self.admin_override_clicked.emit)
        self.admin_override_button.hide()  # Hidden by default

        # --- Button Layout for Admin Override ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.admin_override_button)
        button_layout.addStretch()

        main_layout.addStretch(1)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.subtitle_label)
        main_layout.addSpacing(40)
        main_layout.addLayout(button_layout)
        main_layout.addStretch(1)

        stacked_layout.addWidget(self.background_label)
        stacked_layout.addWidget(foreground_widget)
        
        # Don't set layout here - let the controller handle it
        self.main_layout = stacked_layout
    
    def _load_background_image(self):
        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'thank_you_background.png')
        pixmap = QPixmap(image_path)
        self.background_label.setPixmap(pixmap)
        self.background_label.setScaledContents(True)
    
    def update_status(self, status_text, subtitle_text, status_style):
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(status_style)
        self.subtitle_label.setText(subtitle_text)
    
    def show_admin_override_button(self):
        self.admin_override_button.show()
    
    def hide_admin_override_button(self):
        self.admin_override_button.hide()
    
    def get_admin_button_style(self):
        return (
            "QPushButton { background-color: #8B0000; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } "
            "QPushButton:hover { background-color: #A52A2A; }"
        )
