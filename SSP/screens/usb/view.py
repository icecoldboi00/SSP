import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedLayout,
    QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QColor

def get_base_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

class USBScreenView(QWidget):
    back_button_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.blink_timer = QTimer(self)
        self.setup_ui()
        self.setup_timers()
    
    def setup_ui(self):
        # 1. Main Stacked Layout for Background/Foreground Layering
        main_layout = QStackedLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setStackingMode(QStackedLayout.StackAll)
        self.setLayout(main_layout)

        # 2. Background Layer
        self.background_label = QLabel()
        self._load_background_image()

        # 3. Foreground Layer (contains all UI controls)
        foreground_widget = QWidget()
        foreground_widget.setStyleSheet("background-color: transparent;")
        
        fg_layout = QVBoxLayout(foreground_widget)
        fg_layout.setContentsMargins(20, 20, 20, 20)
        fg_layout.setSpacing(20)

        # --- UI Elements ---
        title = QLabel("INSERT USB FLASHDRIVE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #36454F; font-size: 38px; font-weight: bold;")
        title.setWordWrap(True)

        instruction = QLabel("The system will automatically detect your storage device.")
        instruction.setAlignment(Qt.AlignCenter)
        instruction.setWordWrap(False)
        instruction.setStyleSheet("color: #36454F; font-size: 22px; line-height: 1.4; padding: 10px;")
        instruction.setMaximumWidth(1200)

        self.status_indicator = QLabel("Initializing...")
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self.status_indicator.setMinimumHeight(55)
        self.status_indicator.setStyleSheet(self.get_initial_status_style())
        
        # Button Creation
        self.back_button = QPushButton("← Back to Main")
        self.back_button.setStyleSheet(self.get_back_button_style())
        
        # --- Layout Assembly ---
        fg_layout.addStretch(2)
        fg_layout.addWidget(title, 0, Qt.AlignCenter)
        fg_layout.addSpacing(15)
        fg_layout.addWidget(instruction, 1, Qt.AlignCenter)
        fg_layout.addStretch(1)
        
        status_layout = QHBoxLayout()
        status_layout.addStretch()
        status_layout.addWidget(self.status_indicator)
        status_layout.addStretch()
        fg_layout.addLayout(status_layout)
        
        fg_layout.addSpacing(20)
        fg_layout.addStretch(4)

        nav_buttons_layout = QHBoxLayout()
        nav_buttons_layout.addWidget(self.back_button, 0, Qt.AlignLeft)
        nav_buttons_layout.addStretch()
        fg_layout.addLayout(nav_buttons_layout)

        # 4. Add Layers to Main Layout
        main_layout.addWidget(self.background_label)
        main_layout.addWidget(foreground_widget)
        
        # Set the foreground widget as the active one for interaction
        main_layout.setCurrentWidget(foreground_widget)

        # Connect button signals
        self.back_button.clicked.connect(self.back_button_clicked.emit)
    
    def setup_timers(self):
        self.blink_timer.timeout.connect(self.blink_status)
    
    def _load_background_image(self):
        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'usb_screen background.png')
        pixmap = QPixmap(image_path)
        self.background_label.setPixmap(pixmap)
        self.background_label.setScaledContents(True)
    
    def update_status_indicator(self, text, style_key, color_hex):
        self.status_indicator.setText(text)
        self.status_indicator.setStyleSheet(f"""
            QLabel {{
                color: {color_hex}; font-size: 18px; font-weight: bold;
                padding: 10px 20px; border: 2px solid {color_hex}; border-radius: 8px;
                background-color: rgba({QColor(color_hex).red()}, {QColor(color_hex).green()}, {QColor(color_hex).blue()}, 0.1);
            }}""")
    
    def blink_status(self):
        current_style = self.status_indicator.styleSheet()
        if "0.1" in current_style:
            new_style = current_style.replace("0.1", "0.05")
        else:
            new_style = current_style.replace("0.05", "0.1")
        self.status_indicator.setStyleSheet(new_style)
    
    def start_blinking(self):
        self.blink_timer.start(700)
    
    def stop_blinking(self):
        self.blink_timer.stop()
    
    def get_initial_status_style(self):
        return """
            QLabel {
                color: #555; font-size: 18px; padding: 10px 20px;
                border: 2px solid #ccc; border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.1);
            }"""

    def get_back_button_style(self):
        return """
            QPushButton { 
                background-color: #6c757d; color: white; font-size: 14px;
                border: none; border-radius: 6px; padding: 10px 20px;
            }
            QPushButton:hover { background-color: #5a6268; }
        """
    
    def show_message(self, title, text):
        QMessageBox.information(self, title, text)

