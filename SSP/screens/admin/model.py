# screens/admin/model.py

from PyQt5.QtCore import QObject, pyqtSignal
from database.db_manager import DatabaseManager
from sms_manager import get_sms_manager

class AdminModel(QObject):
    """Handles the data and business logic for the admin screen."""
    paper_count_changed = pyqtSignal(int, str)  # Emits new count and display color
    show_message = pyqtSignal(str, str)         # Emits message title and text

    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.sms_manager = get_sms_manager()
        self.paper_count = 100
        self.sms_alert_sent = False
        
        # Initialize the modem when the model is created
        self.sms_manager.initialize_modem()

    def load_paper_count(self):
        """Loads the paper count from the database and emits a signal."""
        self.paper_count = self.db_manager.get_setting('paper_count', default=100)
        color = self._get_color_for_count(self.paper_count)
        self.paper_count_changed.emit(self.paper_count, color)

    def reset_paper_count(self):
        """Resets the paper count to 100."""
        self.paper_count = 100
        self.db_manager.update_setting('paper_count', self.paper_count)
        self.sms_alert_sent = False
        print("Paper count reset to 100, SMS alert flag reset.")
        self.load_paper_count() # Reload to emit signal

    def update_paper_count_from_string(self, count_str: str):
        """Validates and updates the paper count from user input string."""
        try:
            new_count = int(count_str)
            if not (0 <= new_count <= 100):
                self.show_message.emit("Invalid Input", "Paper count must be between 0 and 100.")
                self.load_paper_count() # Revert display to current value
                return

            old_count = self.paper_count
            self.paper_count = new_count
            self.db_manager.update_setting('paper_count', self.paper_count)

            if new_count > old_count and new_count > 10:
                self.sms_alert_sent = False
            
            self.check_low_paper_alert()
            self.load_paper_count() # Reload to emit signal
            print(f"Paper count updated from {old_count} to {new_count} sheets.")

        except ValueError:
            self.show_message.emit("Invalid Input", "Please enter a valid number.")
            self.load_paper_count() # Revert display

    def decrement_paper_count(self, pages_to_print: int) -> bool:
        """Decrements paper count for a print job. Returns True on success."""
        if self.paper_count >= pages_to_print:
            self.paper_count = max(0, self.paper_count - pages_to_print)
            self.db_manager.update_setting('paper_count', self.paper_count)
            self.check_low_paper_alert()
            self.load_paper_count() # Emit signal to update any listening UI
            print(f"Paper count updated to {self.paper_count} sheets.")
            return True
        else:
            print(f"ERROR: Not enough paper. Required: {pages_to_print}, Available: {self.paper_count}")
            return False

    def check_low_paper_alert(self):
        """Checks for low paper and sends an SMS alert if needed."""
        if self.paper_count <= 10 and not self.sms_alert_sent:
            print(f"Low paper detected: {self.paper_count} sheets remaining. Sending alert.")
            message = f"ALERT: Paper is low ({self.paper_count} sheets left). Please refill soon."
            
            # FIX: Use the correct method from sms_manager
            if self.sms_manager.send_custom_alert(message):
                self.sms_alert_sent = True
                print("Low paper SMS sent successfully.")
            else:
                print("Failed to send low paper SMS.")

        elif self.paper_count > 10:
            self.sms_alert_sent = False

    def _get_color_for_count(self, count: int) -> str:
        """Determines the display color based on the paper count."""
        if count <= 20: return "#dc3545"
        if count <= 50: return "#ffc107"
        return "#28a745"