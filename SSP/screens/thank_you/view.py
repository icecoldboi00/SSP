import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QStackedLayout
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

def get_base_dir():
    """Gets the base directory of the project."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

class ThankYouScreenView(QWidget):
    """View for the Thank You screen - handles UI components and presentation."""
    
    # Signals for user interactions
    finish_button_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Sets up the user interface for the screen."""
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

        self.status_label = QLabel("FILE PRINTING IN PROGRESS...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #36454F; font-size: 42px; font-weight: bold;")

        self.subtitle_label = QLabel("Please wait a moment.")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("color: #36454F; font-size: 24px;")

        # --- Simulation Button (Now hidden, kept for potential future testing) ---
        self.finish_button = QPushButton("Simulate Print Finished")
        self.finish_button.setMinimumHeight(50)
        self.finish_button.setMaximumWidth(400)
        self.finish_button.setStyleSheet(self.get_finish_button_style())
        self.finish_button.clicked.connect(self.finish_button_clicked.emit)
        self.finish_button.hide()  # Hide the button, printing is now automatic

        main_layout.addStretch(1)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.subtitle_label)
        main_layout.addSpacing(40)
        main_layout.addWidget(self.finish_button, 0, Qt.AlignHCenter)
        main_layout.addStretch(1)

        stacked_layout.addWidget(self.background_label)
        stacked_layout.addWidget(foreground_widget)
        
        # Don't set layout here - let the controller handle it
        self.main_layout = stacked_layout
    
    def _load_background_image(self):
        """Loads the background image."""
        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'thank_you_background.png')
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.background_label.setPixmap(pixmap)
            self.background_label.setScaledContents(True)
        else:
            print(f"WARNING: Background image not found at '{image_path}'.")
            self.background_label.setStyleSheet("background-color: #1f1f38;")
    
    def update_status(self, status_text, subtitle_text, status_style):
        """Updates the status and subtitle labels with the provided text and style."""
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(status_style)
        self.subtitle_label.setText(subtitle_text)
    
    def get_finish_button_style(self):
        """Returns the style for the finish button."""
        return """
            QPushButton { 
                background-color: #1e440a; color: white; font-size: 18px;
                font-weight: bold; border: none; border-radius: 8px; 
            }
            QPushButton:hover { background-color: #2a5d1a; }
        """
