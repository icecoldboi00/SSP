from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QSpacerItem, QSizePolicy, QDialog)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QPalette

from screens.pin_dialog import PinDialog

class IdleScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.setup_ui()
    
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
        frame_layout.setSpacing(40)
        
        # Title
        title = QLabel("SELF SERVICE PRINTING KIOSK")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 48px;
                font-weight: bold;
                margin: 30px;
            }
        """)
        
        # Main action button
        start_button = QPushButton("START PRINTING")
        start_button.setMinimumHeight(80)
        start_button.setMaximumWidth(800)
        start_button.setStyleSheet("""
            QPushButton {
                background-color: #2d5aa0;
                color: white;
                font-size: 24px;
                font-weight: bold;
                border: none;
                border-radius: 15px;
                padding: 20px;
                margin: 30px;
            }
            QPushButton:hover {
                background-color: #3d6ab0;
            }
            QPushButton:pressed {
                background-color: #1d4a90;
            }
        """)
        start_button.clicked.connect(self.start_printing)
        
        # --- Original Layout Spacing ---
        frame_layout.addItem(QSpacerItem(20, 60, QSizePolicy.Minimum, QSizePolicy.Expanding))
        frame_layout.addWidget(title)
        frame_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))
        
        button_layout = QHBoxLayout()
        button_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        button_layout.addWidget(start_button)
        button_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        frame_layout.addLayout(button_layout)
        
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
        
        frame_layout.addStretch(1)
        # --- End Original Layout Spacing ---

        # Admin Button
        admin_button = QPushButton("Admin")
        admin_button.setFixedSize(90, 35)
        admin_button.setStyleSheet("""
            QPushButton {
                background-color: #3a3a5a;
                color: #cccccc;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #4a4a6a;
                border-color: #777;
            }
        """)
        admin_button.clicked.connect(self.go_to_admin)
        
        admin_layout = QHBoxLayout()
        admin_layout.addStretch(1)
        admin_layout.addWidget(admin_button)
        
        frame_layout.addLayout(admin_layout)

        layout.addWidget(main_frame)
        self.setLayout(layout)
    
    def start_printing(self):
        """Navigate to USB screen"""
        self.main_app.show_screen('usb')

    def go_to_admin(self):
        """
        Show the PIN dialog and navigate to the admin screen
        only if the correct PIN is entered.
        """
        dialog = PinDialog(self)
        # .exec_() shows the dialog and waits until it's closed.
        # It returns QDialog.Accepted if self.accept() was called inside the dialog.
        result = dialog.exec_()

        if result == QDialog.Accepted:
            print("PIN Accepted. Navigating to admin screen.")
            self.main_app.show_screen('admin')
        else:
            print("PIN Dialog closed without correct PIN.")
    
    def on_enter(self):
        """Called when screen becomes active"""
        pass
    
    def on_leave(self):
        """Called when leaving screen"""
        pass