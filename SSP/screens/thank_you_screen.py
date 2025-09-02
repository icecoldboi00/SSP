import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QStackedLayout
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap

def get_base_dir():
    """Gets the base directory of the project."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class ThankYouScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.redirect_timer = QTimer(self)
        self.redirect_timer.setSingleShot(True)
        self.redirect_timer.timeout.connect(self.go_to_idle)
        self.setup_ui()

    def setup_ui(self):
        """Sets up the user interface for the screen."""
        stacked_layout = QStackedLayout()
        stacked_layout.setContentsMargins(0, 0, 0, 0)
        stacked_layout.setStackingMode(QStackedLayout.StackAll)

        # --- Background ---
        background_label = QLabel()
        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'thank_you_background.png')
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            background_label.setPixmap(pixmap)
            background_label.setScaledContents(True)
        else:
            print(f"WARNING: Background image not found at '{image_path}'.")
            background_label.setStyleSheet("background-color: #1f1f38;")

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

        # --- Simulation Button (for testing) ---
        self.finish_button = QPushButton("Simulate Print Finished")
        self.finish_button.setMinimumHeight(50)
        self.finish_button.setMaximumWidth(400)
        self.finish_button.setStyleSheet("""
            QPushButton { 
                background-color: #1e440a; color: white; font-size: 18px;
                font-weight: bold; border: none; border-radius: 8px; 
            }
            QPushButton:hover { background-color: #2a5d1a; }
        """)
        self.finish_button.clicked.connect(self.finish_printing)

        main_layout.addStretch(1)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(self.subtitle_label)
        main_layout.addSpacing(40)
        main_layout.addWidget(self.finish_button, 0, Qt.AlignHCenter)
        main_layout.addStretch(1)

        stacked_layout.addWidget(background_label)
        stacked_layout.addWidget(foreground_widget)
        self.setLayout(stacked_layout)

    def on_enter(self):
        """Called when the screen is shown."""
        # Reset to the initial state every time we enter
        self.status_label.setText("FILE PRINTING IN PROGRESS...")
        self.subtitle_label.setText("Please wait a moment.")
        self.finish_button.show()
        self.redirect_timer.stop()
        
        # In a real scenario, you would listen for a signal from the printer queue.
        # For now, the user must click the simulation button.

    def finish_printing(self):
        """Updates the UI to the finished state and starts the timer."""
        self.status_label.setText("PRINTING HAS FINISHED")
        self.subtitle_label.setText("Kindly collect your documents. We hope to see you again!")
        self.finish_button.hide() # Hide the button after use
        
        # Start the 5-second timer to go back to the idle screen
        self.redirect_timer.start(5000)

    def go_to_idle(self):
        """Navigates back to the idle screen."""
        self.main_app.show_screen('idle')

    def on_leave(self):
        """Called when the screen is hidden."""
        # Stop the timer if the user navigates away manually
        if self.redirect_timer.isActive():
            self.redirect_timer.stop()