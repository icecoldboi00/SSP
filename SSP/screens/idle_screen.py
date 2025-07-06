from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPalette

class IdleScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.setup_ui()
        self.setup_timer()
    
    def setup_ui(self):
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create main frame with background
        main_frame = QFrame()
        main_frame.setStyleSheet("""
            QFrame {
                background-color: #0f0f1f;
                border: none;
            }
        """)
        
        frame_layout = QVBoxLayout(main_frame)
        frame_layout.setContentsMargins(50, 50, 50, 50)
        frame_layout.setSpacing(30)
        
        # Title
        title = QLabel("PRINTING SYSTEM")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 48px;
                font-weight: bold;
                margin: 20px;
            }
        """)
        
        # Subtitle
        subtitle = QLabel("Touch screen to start printing")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 24px;
                margin: 10px;
            }
        """)
        
        # Status indicator
        self.status_label = QLabel("System Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #00ff00;
                font-size: 18px;
                margin: 10px;
                padding: 10px;
                border: 2px solid #00ff00;
                border-radius: 10px;
                background-color: rgba(0, 255, 0, 0.1);
            }
        """)
        
        # Main action button
        start_button = QPushButton("START PRINTING")
        start_button.setMinimumHeight(80)
        start_button.setStyleSheet("""
            QPushButton {
                background-color: #2d5aa0;
                color: white;
                font-size: 24px;
                font-weight: bold;
                border: none;
                border-radius: 15px;
                padding: 20px;
                margin: 20px;
            }
            QPushButton:hover {
                background-color: #3d6ab0;
            }
            QPushButton:pressed {
                background-color: #1d4a90;
            }
        """)
        start_button.clicked.connect(self.start_printing)
        
        # Instructions
        instructions = QLabel("Insert USB drive with PDF files\nSystem will automatically detect and process files")
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setStyleSheet("""
            QLabel {
                color: #aaaaaa;
                font-size: 16px;
                line-height: 1.5;
                margin: 20px;
            }
        """)
        
        # Add spacers and widgets
        frame_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        frame_layout.addWidget(title)
        frame_layout.addWidget(subtitle)
        frame_layout.addWidget(self.status_label)
        frame_layout.addWidget(start_button)
        frame_layout.addWidget(instructions)
        frame_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Bottom info
        bottom_info = QLabel("Supported formats: PDF files only")
        bottom_info.setAlignment(Qt.AlignCenter)
        bottom_info.setStyleSheet("""
            QLabel {
                color: #666666;
                font-size: 14px;
                margin: 10px;
            }
        """)
        frame_layout.addWidget(bottom_info)
        
        layout.addWidget(main_frame)
        self.setLayout(layout)
    
    def setup_timer(self):
        """Setup timer for status blinking effect"""
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.blink_status)
        self.blink_timer.start(1000)  # Blink every second
        self.blink_state = True
    
    def blink_status(self):
        """Animate status indicator"""
        if self.blink_state:
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #00ff00;
                    font-size: 18px;
                    margin: 10px;
                    padding: 10px;
                    border: 2px solid #00ff00;
                    border-radius: 10px;
                    background-color: rgba(0, 255, 0, 0.1);
                }
            """)
        else:
            self.status_label.setStyleSheet("""
                QLabel {
                    color: #00ff00;
                    font-size: 18px;
                    margin: 10px;
                    padding: 10px;
                    border: 2px solid #00ff00;
                    border-radius: 10px;
                    background-color: rgba(0, 255, 0, 0.05);
                }
            """)
        self.blink_state = not self.blink_state
    
    def start_printing(self):
        """Navigate to USB screen"""
        self.main_app.show_screen('usb')
    
    def on_enter(self):
        """Called when screen becomes active"""
        if hasattr(self, 'blink_timer'):
            self.blink_timer.start(1000)
    
    def on_leave(self):
        """Called when leaving screen"""
        if hasattr(self, 'blink_timer'):
            self.blink_timer.stop()
