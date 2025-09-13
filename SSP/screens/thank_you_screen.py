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

        # --- Simulation Button (Now hidden, kept for potential future testing) ---
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
        self.finish_button.hide() # Hide the button, printing is now automatic

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
        # Reset to the initial "printing in progress" state every time
        self.status_label.setText("SENDING TO PRINTER...")
        self.status_label.setStyleSheet("color: #36454F; font-size: 42px; font-weight: bold;")
        self.subtitle_label.setText("Please wait while we process your print job.")
        self.redirect_timer.stop()
        
    def finish_printing(self):
        """Updates the UI to the finished state and starts the timer to go idle."""
        self.status_label.setText("PRINTING COMPLETED")
        self.status_label.setStyleSheet("color: #28a745; font-size: 42px; font-weight: bold;")  # Green color
        self.subtitle_label.setText("Kindly collect your documents. We hope to see you again!")
        
        # Start the 5-second timer to go back to the idle screen
        self.redirect_timer.start(5000)

    def show_waiting_for_print(self):
        """Updates the UI to show that we're waiting for the actual printing to complete."""
        self.status_label.setText("PRINTING IN PROGRESS...")
        self.status_label.setStyleSheet("color: #ffc107; font-size: 42px; font-weight: bold;")  # Yellow color
        self.subtitle_label.setText("Please wait while your document is being printed.")

    def show_printing_error(self, message: str):
        """Updates the UI to show a printing error."""
        self.status_label.setText("PRINTING FAILED")
        self.status_label.setStyleSheet("color: #dc3545; font-size: 42px; font-weight: bold;") # Red color
        
        # Sanitize common, verbose CUPS errors for a better user display
        if "client-error-document-format-not-supported" in message:
            clean_message = "Document format is not supported by the printer."
        elif "CUPS Error" in message:
            clean_message = "Could not communicate with the printer."
        else:
            clean_message = "An unknown printing error occurred."

        self.subtitle_label.setText(f"Error: {clean_message}\nPlease contact an administrator.")
        
        # Start a longer timer to allow the user to read the error
        self.redirect_timer.start(15000)

    def go_to_idle(self):
        """Navigates back to the idle screen."""
        self.main_app.show_screen('idle')

    def on_leave(self):
        """Called when the screen is hidden."""
        # Stop the timer if the user navigates away manually (unlikely here)
        if self.redirect_timer.isActive():
            self.redirect_timer.stop()