# screens/usb/view.py

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
    """The user interface for the USB Screen. Contains no logic."""
    scan_button_clicked = pyqtSignal()
    test_button_clicked = pyqtSignal()
    clean_button_clicked = pyqtSignal()
    back_button_clicked = pyqtSignal()
    cancel_button_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.blink_timer = QTimer(self)
        self.setup_ui()
        self.setup_timers()
    
    def setup_ui(self):
        """Initializes the user interface using a flexible, layered layout."""
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
        fg_layout.setContentsMargins(40, 30, 40, 30)
        fg_layout.setSpacing(15)

        # --- UI Elements ---
        title = QLabel("INSERT USB FLASHDRIVE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #36454F; font-size: 38px; font-weight: bold;")
        title.setWordWrap(True)

        instruction = QLabel("The system will automatically detect your drive. If it doesn't appear, you can try a manual scan.")
        instruction.setAlignment(Qt.AlignCenter)
        instruction.setWordWrap(True)
        instruction.setStyleSheet("color: #36454F; font-size: 22px; line-height: 1.4;")
        instruction.setMaximumWidth(800)

        self.status_indicator = QLabel("Initializing...")
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self.status_indicator.setMinimumHeight(55)
        self.status_indicator.setStyleSheet(self.get_initial_status_style())

        # Button Creation
        self.scan_button = QPushButton("Manual Scan")
        self.scan_button.setStyleSheet(self.get_action_button_style())
        
        self.test_button = QPushButton("TEST: Simulate PDF")
        self.test_button.setStyleSheet(self.get_action_button_style())
        
        self.clean_button = QPushButton("Clean Temp Files")
        self.clean_button.setStyleSheet(self.get_action_button_style())

        self.back_button = QPushButton("← Back to Main")
        self.back_button.setStyleSheet(self.get_back_button_style())
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet(self.get_cancel_button_style())
        
        # --- Layout Assembly ---
        fg_layout.addStretch(3)
        fg_layout.addWidget(title, 0, Qt.AlignCenter)
        fg_layout.addSpacing(10)
        fg_layout.addWidget(instruction, 0, Qt.AlignCenter)
        fg_layout.addStretch(1)
        
        status_layout = QHBoxLayout()
        status_layout.addStretch()
        status_layout.addWidget(self.status_indicator)
        status_layout.addStretch()
        fg_layout.addLayout(status_layout)
        fg_layout.addSpacing(20)

        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.addStretch()
        action_buttons_layout.addWidget(self.scan_button)
        action_buttons_layout.addSpacing(20)
        action_buttons_layout.addWidget(self.test_button)
        action_buttons_layout.addSpacing(20)
        action_buttons_layout.addWidget(self.clean_button)
        action_buttons_layout.addStretch()
        fg_layout.addLayout(action_buttons_layout)
        fg_layout.addStretch(4)

        nav_buttons_layout = QHBoxLayout()
        nav_buttons_layout.addWidget(self.back_button, 0, Qt.AlignLeft)
        nav_buttons_layout.addStretch()
        nav_buttons_layout.addWidget(self.cancel_button, 0, Qt.AlignRight)
        fg_layout.addLayout(nav_buttons_layout)

        # 4. Add Layers to Main Layout
        main_layout.addWidget(self.background_label)
        main_layout.addWidget(foreground_widget)
        
        # Set the foreground widget as the active one for interaction
        main_layout.setCurrentWidget(foreground_widget)

        # Connect button signals
        self.scan_button.clicked.connect(self.scan_button_clicked.emit)
        self.test_button.clicked.connect(self.test_button_clicked.emit)
        self.clean_button.clicked.connect(self.clean_button_clicked.emit)
        self.back_button.clicked.connect(self.back_button_clicked.emit)
        self.cancel_button.clicked.connect(self.cancel_button_clicked.emit)
    
    def setup_timers(self):
        """Sets up timers for the view."""
        self.blink_timer.timeout.connect(self.blink_status)
    
    def _load_background_image(self):
        """Loads the background image."""
        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'usb_screen background.png')
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.background_label.setPixmap(pixmap)
            self.background_label.setScaledContents(True)
        else:
            print(f"WARNING: Background image not found at '{image_path}'")
            self.background_label.setStyleSheet("background-color: #e0e0e0;")
    
    def update_status_indicator(self, text, style_key, color_hex):
        """Updates the text and style of the status indicator label."""
        self.status_indicator.setText(text)
        self.status_indicator.setStyleSheet(f"""
            QLabel {{
                color: {color_hex}; font-size: 18px; font-weight: bold;
                padding: 10px 20px; border: 2px solid {color_hex}; border-radius: 8px;
                background-color: rgba({QColor(color_hex).red()}, {QColor(color_hex).green()}, {QColor(color_hex).blue()}, 0.1);
            }}""")
    
    def blink_status(self):
        """Toggles the opacity of the status indicator for a blinking effect."""
        current_style = self.status_indicator.styleSheet()
        if "0.1" in current_style:
            new_style = current_style.replace("0.1", "0.05")
        else:
            new_style = current_style.replace("0.05", "0.1")
        self.status_indicator.setStyleSheet(new_style)
    
    def start_blinking(self):
        """Starts the blinking effect."""
        self.blink_timer.start(700)
    
    def stop_blinking(self):
        """Stops the blinking effect."""
        self.blink_timer.stop()
    
    def show_cleanup_confirmation(self):
        """Shows confirmation dialog for cleanup."""
        reply = QMessageBox.question(self, 'Confirm Cleanup', 
                                     'This will delete all copied temporary files. Are you sure?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return reply == QMessageBox.Yes
    
    def show_message(self, title, text):
        """Shows a message to the user."""
        QMessageBox.information(self, title, text)
    
    def show_warning(self, title, text):
        """Shows a warning message to the user."""
        QMessageBox.warning(self, title, text)
    
    def get_initial_status_style(self):
        """Returns the initial style for the status indicator."""
        return """
            QLabel {
                color: #555; font-size: 18px; padding: 10px 20px;
                border: 2px solid #ccc; border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.1);
            }"""

    def get_action_button_style(self):
        """Returns the style for action buttons."""
        return """
            QPushButton {
                background-color: #1e440a; color: white; font-size: 15px;
                font-weight: bold; border: none; border-radius: 8px; 
                padding: 12px 24px;
            }
            QPushButton:hover { background-color: #2a5d1a; }
            QPushButton:pressed { background-color: #142e07; }
        """

    def get_back_button_style(self):
        """Returns the style for the back button."""
        return """
            QPushButton { 
                background-color: #6c757d; color: white; font-size: 14px;
                border: none; border-radius: 6px; padding: 10px 20px;
            }
            QPushButton:hover { background-color: #5a6268; }
        """

    def get_cancel_button_style(self):
        """Returns the style for the cancel button."""
        return """
            QPushButton { 
                background-color: #c82333; color: white; font-size: 14px;
                border: none; border-radius: 6px; padding: 10px 20px;
            }
            QPushButton:hover { background-color: #a51c2a; }
        """
