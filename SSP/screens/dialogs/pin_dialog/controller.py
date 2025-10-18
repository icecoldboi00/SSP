from PyQt5.QtWidgets import QDialog
from .model import PinDialogModel
from .view import PinDialogView

class PinDialogController(PinDialogView):
    """Controller for the PIN Dialog - coordinates between model and view."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.model = PinDialogModel()
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect signals from the view to the model and vice-versa."""
        # --- View -> Controller -> Model ---
        self.number_clicked.connect(self.model.add_digit)
        self.clear_clicked.connect(self.model.clear_pin)
        self.enter_clicked.connect(self._validate_pin)
        
        # --- Model -> Controller -> View ---
        self.model.pin_updated.connect(self.update_pin_display)
        self.model.status_updated.connect(self.update_status)
        self.model.pin_validated.connect(self._handle_pin_validation)
    
    def _validate_pin(self):
        """Handles PIN validation."""
        try:
            is_valid = self.model.validate_pin()
            # Don't call accept() here - let _handle_pin_validation handle it
        except Exception as e:
            print(f"Error validating PIN: {e}")
            self.update_status("Error occurred")
    
    def _handle_pin_validation(self, is_valid):
        """Handles the result of PIN validation."""
        try:
            if is_valid:
                print("PIN validated successfully")
                self.accept()  # Close dialog with success
            else:
                print("PIN validation failed")
        except Exception as e:
            print(f"Error handling PIN validation: {e}")
            self.update_status("Error occurred")
