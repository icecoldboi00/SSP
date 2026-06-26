from PyQt5.QtWidgets import QWidget, QDialog
from .model import ThankYouModel
from .view import ThankYouScreenView
from screens.dialogs.pin_dialog import PinDialogController as PinDialog

class ThankYouController(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        
        self.model = ThankYouModel()
        self.model.main_app = main_app  # Pass main_app reference to model
        self.view = ThankYouScreenView()
        
        # Set the view's layout as this controller's layout
        self.setLayout(self.view.main_layout)
        
        self._connect_signals()
    
    def _connect_signals(self):
        self.view.admin_override_clicked.connect(self._handle_admin_override)
        
        # --- Model -> View ---
        self.model.status_updated.connect(self._update_status_display)
        self.model.redirect_to_idle.connect(self._go_to_idle)
        self.model.admin_override_requested.connect(self._show_admin_override_button)
        self.model.admin_override_hidden.connect(self._hide_admin_override_button)
    
    def _update_status_display(self, status_text, subtitle_text):
        status_style = self.model.get_status_style(self.model.current_state)
        self.view.update_status(status_text, subtitle_text, status_style)
    
    def _go_to_idle(self):
        self.main_app.show_screen('idle')
    
    def on_enter(self):
        # Ensure admin override button is hidden when entering screen
        self.view.hide_admin_override_button()
        self.model.on_enter(self.main_app)
    
    def on_leave(self):
        # Ensure admin override button is hidden when leaving screen
        self.view.hide_admin_override_button()
        self.model.on_leave()
    
    def show_waiting_for_print(self):
        self.model.show_waiting_for_print()
    
    def show_printing_error(self, message: str):
        self.model.show_printing_error(message)
    
    def show_paper_jam_error(self, message: str):
        self.model.show_paper_jam_error(message)
    
    def show_no_paper_error(self, paper_count: int):
 
        self.model.show_no_paper_error(paper_count)

    def show_low_coins_error(self, peso_1_count: int, peso_5_count: int):
        message = (
            "Machine is low on coins for change.\n"
            f"₱1 Coins: {peso_1_count} remaining | ₱5 Coins: {peso_5_count} remaining\n\n"
            "Please contact an administrator to refill the coins."
        )
        # We can reuse the printing error state in the model to show the message
        self.model.show_printing_error(message)
        
        # Explicitly show the admin override button so the admin can bypass the screen
        self._show_admin_override_button()
    
    def _show_admin_override_button(self):
        print("Showing admin override")
        self.view.show_admin_override_button()
    
    def _hide_admin_override_button(self):
        self.view.hide_admin_override_button()
    
    def _handle_admin_override(self):
        dialog = PinDialog(self)
        result = dialog.exec_()
        if result == QDialog.Accepted:
            print("PIN accepted")
            self.model.handle_admin_override()
        else:
            print("Wrong PIN")
