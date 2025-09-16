# screens/admin_screen.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame,
    QDialog, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIntValidator, QPixmap, QPainter
from database.db_manager import DatabaseManager
from sms_manager import get_sms_manager, initialize_sms
from .data_viewer_screen import DataViewerScreen  # <-- New import statement

# The DataViewerScreen class has been moved to data_viewer_screen.py
# and is now imported above. The AdminScreen class remains here.

class AdminScreen(QWidget):
    def __init__(self, main_app, background_image_path=None):
        super().__init__()
        self.main_app = main_app
        self.db_manager = DatabaseManager()
        self.paper_count = self.load_paper_count_from_db()
        self.sms_alert_sent = False  # Track if low paper SMS has been sent

        self.background_pixmap = None
        if background_image_path:
            self.background_pixmap = QPixmap(background_image_path)

        self.setup_ui()
        self.update_paper_display() # Update display on first load
        self.initialize_sms_system()

    def paintEvent(self, event):
        """Draws the background image."""
        painter = QPainter(self)
        if self.background_pixmap:
            painter.drawPixmap(self.rect(), self.background_pixmap)
        else:
            # Fallback background color if no image is provided
            painter.fillRect(self.rect(), Qt.GlobalColor.black) # Use a color from the theme, e.g., #1f1f38
        super().paintEvent(event)

    def resizeEvent(self, event):
        """Ensures the background is redrawn on resize."""
        self.update()
        super().resizeEvent(event)

    def setup_ui(self):
        # The main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.setSpacing(20)

        # --- Title ---
        title = QLabel("Admin Panel")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-size: 48px; font-weight: bold; text-shadow: 2px 2px 4px #000000;")

        # --- Main Content Container ---
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_frame.setStyleSheet("""
            #contentFrame {
                background-color: rgba(15, 31, 0, 0.85); /* Semi-transparent dark green */
                border: 1px solid rgba(42, 93, 26, 0.9);
                border-radius: 20px;
            }
        """)
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(25)

        # --- Paper Management Section ---
        paper_group = self.create_paper_management_group()

        # --- Data & System Section ---
        system_group = self.create_system_data_group()

        # Add widgets to content layout
        content_layout.addWidget(paper_group)
        content_layout.addWidget(system_group)

        # --- Back Button ---
        back_button = QPushButton("← Back to Main Screen")
        back_button.setMinimumHeight(60)
        back_button.setCursor(Qt.PointingHandCursor)
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #c83c3c; /* Reddish color */
                color: white;
                font-size: 20px;
                font-weight: bold;
                border: 1px solid #d85050;
                border-radius: 10px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #e05a5a;
            }
        """)
        back_button.clicked.connect(self.go_back)

        # Add main widgets to the screen layout
        layout.addWidget(title)
        layout.addWidget(content_frame, 1) # Add stretch factor
        layout.addWidget(back_button)

        self.setLayout(layout)

    def create_paper_management_group(self):
        """Creates the 'Paper Management' group box."""
        group = QGroupBox("Paper Management")
        group.setStyleSheet(self.get_groupbox_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Paper count display and input
        count_layout = QHBoxLayout()
        paper_label = QLabel("Current Paper Count:")
        paper_label.setStyleSheet("color: #e0e0e0; font-size: 18px;")

        self.paper_count_input = QLineEdit()
        self.paper_count_input.setText(str(self.paper_count))
        self.paper_count_input.setValidator(QIntValidator(0, 100))
        self.paper_count_input.setAlignment(Qt.AlignCenter)
        self.paper_count_input.setFixedWidth(100)
        self.paper_count_input.returnPressed.connect(self.update_paper_count_from_input)
        self.paper_count_input.editingFinished.connect(self.update_paper_count_from_input)

        count_layout.addWidget(paper_label)
        count_layout.addStretch()
        count_layout.addWidget(self.paper_count_input)

        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        update_paper_btn = QPushButton("Update Count")
        update_paper_btn.setStyleSheet(self.get_button_style("#ff9800", "#f57c00")) # Orange theme
        update_paper_btn.clicked.connect(self.update_paper_count_from_input)

        reset_paper_btn = QPushButton("Refill (Reset to 100)")
        reset_paper_btn.setStyleSheet(self.get_button_style("#1e440a", "#2a5d1a")) # Green theme
        reset_paper_btn.clicked.connect(self.reset_paper_count)

        button_layout.addStretch()
        button_layout.addWidget(update_paper_btn)
        button_layout.addWidget(reset_paper_btn)
        button_layout.addStretch()

        layout.addLayout(count_layout)
        layout.addLayout(button_layout)
        return group

    def create_system_data_group(self):
        """Creates the 'System & Data' group box."""
        group = QGroupBox("System & Data")
        group.setStyleSheet(self.get_groupbox_style())
        layout = QVBoxLayout(group)
        layout.setSpacing(15)

        # Data Viewer Button
        transaction_btn = QPushButton("View System Data Logs")
        transaction_btn.setMinimumHeight(50)
        transaction_btn.setStyleSheet(self.get_button_style("#1e440a", "#2a5d1a", font_size="18px")) # Green theme
        transaction_btn.clicked.connect(self.show_data_viewer)

        # Ink Level (Placeholder)
        ink_layout = QHBoxLayout()
        ink_label = QLabel("Ink Level Status:")
        ink_label.setStyleSheet("color: #e0e0e0; font-size: 18px;")
        ink_placeholder = QLabel("Monitoring Not Implemented")
        ink_placeholder.setStyleSheet("color: #999999; font-size: 18px; font-style: italic;")
        ink_layout.addWidget(ink_label)
        ink_layout.addStretch()
        ink_layout.addWidget(ink_placeholder)

        layout.addWidget(transaction_btn)
        layout.addLayout(ink_layout)
        return group

    def get_groupbox_style(self):
        return """
            QGroupBox {
                font-size: 22px;
                font-weight: bold;
                color: white;
                border: 1px solid #2a5d1a;
                border-radius: 10px;
                margin-top: 10px;
                background-color: rgba(30, 68, 10, 0.6); /* Semi-transparent green */
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 5px 15px;
                background-color: #1e440a; /* Dark Green theme for title */
                border-radius: 5px;
            }
        """

    def get_button_style(self, bg_color, hover_color, font_size="16px"):
        return f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                font-size: {font_size};
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 12px 25px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
        """

    def go_back(self):
        self.main_app.show_screen('idle')

    def on_enter(self):
        """Called when this screen becomes active. Reloads data from DB."""
        print("DEBUG: Admin screen entered. Refreshing data.")
        self.paper_count = self.load_paper_count_from_db()
        self.update_paper_display()
        
    def load_paper_count_from_db(self):
        """Loads the current paper count from the database."""
        return self.db_manager.get_setting('paper_count', default=100)

    def reset_paper_count(self):
        """Reset paper count to 100 sheets and save to DB."""
        self.paper_count = 100
        self.db_manager.update_setting('paper_count', self.paper_count)
        self.update_paper_display()
        self.sms_alert_sent = False  # Reset SMS alert flag when paper is refilled
        print("DEBUG: Paper count reset to 100 sheets, SMS alert flag reset")

    def update_paper_count(self, pages_to_print):
        """Update paper count and save to DB. Returns True if enough paper."""
        if self.paper_count >= pages_to_print:
            self.paper_count = max(0, self.paper_count - pages_to_print)
            self.db_manager.update_setting('paper_count', self.paper_count)
            self.update_paper_display()
            print(f"DEBUG: Paper count updated to {self.paper_count} sheets")
            
            # Check for low paper and send SMS alert
            self.check_low_paper_alert()
            
            return True
        print(f"ERROR: Not enough paper. Required: {pages_to_print}, Available: {self.paper_count}")
        return False

    def update_paper_display(self):
        """Update the paper count input field and its color based on the amount."""
        self.paper_count_input.setText(str(self.paper_count))
        
        if self.paper_count <= 20:
            color = "#dc3545"  # Red for critical
        elif self.paper_count <= 50:
            color = "#ffc107"  # Yellow for warning
        else:
            color = "#28a745"  # Green for good
            
        self.paper_count_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: #1f1f38;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: 3px solid {color};
                border-radius: 8px;
                padding: 5px 10px;
            }}
            QLineEdit:focus {{
                border: 3px solid #ff9800; /* Orange theme for focus */
            }}
        """)

    def get_paper_count(self):
        return self.paper_count

    def update_paper_count_from_input(self):
        """Update paper count from the input field with validation."""
        try:
            new_count = int(self.paper_count_input.text())
            
            # Validate range (0-100)
            if new_count < 0:
                new_count = 0
                QMessageBox.warning(self, "Invalid Input", "Paper count cannot be negative. Set to 0.")
            elif new_count > 100:
                new_count = 100
                QMessageBox.warning(self, "Invalid Input", "Maximum paper count is 100 sheets. Set to 100.")
            
            # Update paper count
            old_count = self.paper_count
            self.paper_count = new_count
            self.db_manager.update_setting('paper_count', self.paper_count)
            self.update_paper_display()
            
            # Reset SMS alert flag if paper count increased
            if new_count > old_count and new_count > 10:
                self.sms_alert_sent = False
                print("Paper count increased, SMS alert flag reset")
            
            # Check for low paper alert if count decreased
            if new_count < old_count:
                self.check_low_paper_alert()
            
            print(f"DEBUG: Paper count updated from {old_count} to {new_count} sheets")
            
        except ValueError:
            # Invalid input, reset to current value
            self.paper_count_input.setText(str(self.paper_count))
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number between 0 and 100.")
        except Exception as e:
            print(f"Error updating paper count: {e}")
            self.paper_count_input.setText(str(self.paper_count))

    def initialize_sms_system(self):
        """Initialize the SMS system for low paper alerts."""
        try:
            print("Initializing SMS system...")
            sms_manager = get_sms_manager()
            if sms_manager.initialize_modem():
                print("SMS system initialized successfully")
            else:
                print("SMS system initialization failed - alerts will be disabled")
        except Exception as e:
            print(f"Error initializing SMS system: {e}")

    def check_low_paper_alert(self):
        """Check if paper count is low and send SMS alert if needed."""
        if self.paper_count <= 10 and not self.sms_alert_sent:
            print(f"Low paper detected: {self.paper_count} sheets remaining")
            self.send_low_paper_sms()
        elif self.paper_count > 10:
            # Reset the alert flag when paper is refilled
            self.sms_alert_sent = False
            print("Paper count restored, SMS alert flag reset")

    def send_low_paper_sms(self):
        """Send SMS alert for low paper count."""
        try:
            sms_manager = get_sms_manager()
            message = f"ALERT: Paper is low ({self.paper_count} sheets left) in the printing machine. Please refill soon."
            # Replace with the actual admin phone number or fetch from settings
            admin_phone = self.db_manager.get_setting('admin_phone', default=None)
            if admin_phone:
                sms_manager.send_sms(admin_phone, message)
                self.sms_alert_sent = True
                print(f"Low paper SMS sent to {admin_phone}")
            else:
                print("Admin phone number not set. SMS not sent.")
        except Exception as e:
            print(f"Error sending low paper SMS: {e}")
        

    def show_data_viewer(self):
        """Switches to the data viewer screen."""
        self.main_app.show_screen('data_viewer')