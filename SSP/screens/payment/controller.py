import os
from PyQt5.QtWidgets import QWidget, QMessageBox
from PyQt5.QtCore import pyqtSignal, QTimer
from .model import PaymentModel
from .view import PaymentScreenView

class PaymentController(QWidget):
    payment_completed = pyqtSignal(dict)
    go_back_to_viewer = pyqtSignal(dict)
    
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        
        self.model = PaymentModel(main_app)
        self.view = PaymentScreenView()
        
        # 5 minutes timeout
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._on_timeout) # Back to idle screen
        
        self.setLayout(self.view.main_layout)
        
        self._connect_signals()
    
    def _connect_signals(self):
        self.view.back_button_clicked.connect(self._handle_back_button_clicked)
    
        self.model.payment_data_updated.connect(self.view.update_payment_data)
        self.model.payment_status_updated.connect(self._on_payment_status_updated)
        self.model.amount_received_updated.connect(self._on_amount_received_updated)
        self.model.change_updated.connect(self.view.update_change_display)
        self.model.suggestion_updated.connect(self.view.update_inline_suggestion)
        self.model.payment_completed.connect(self._handle_payment_completed)
        self.model.go_back_requested.connect(self._go_back)
    
        self.view.back_button_clicked.connect(self._reset_timeout)
        self.model.amount_received_updated.connect(self._reset_timeout)
        self.model.change_updated.connect(self._reset_timeout)
        self.model.payment_status_updated.connect(self._reset_timeout)

    def _handle_payment_completed(self, payment_info):
        if 'navigate_to' in payment_info:
            if payment_info['navigate_to'] == 'thank_you':
                self.main_app.show_screen('thank_you')
        else:
            self.payment_completed.emit(payment_info)
            self.view.set_buttons_enabled(False)
    
    def _on_payment_status_updated(self, status_text):
        self.view.update_payment_status(status_text)
        # Disable button when payment is completing
        if "Payment sufficient" in status_text or "Dispensing change" in status_text:
            self.view.set_buttons_enabled(False)
    
    def _on_amount_received_updated(self, amount):
        self.view.update_amount_received(amount)
        # Change button to "Cancel" if any payment has been made (but not if payment is completing)
        if amount > 0 and not (hasattr(self.model, '_payment_completing') and self.model._payment_completing):
            self.view.set_back_button_to_cancel()
        else:
            self.view.set_back_button_to_normal()
    
    def _handle_back_button_clicked(self):
        # Prevent cancellation if payment is already completing
        if hasattr(self.model, '_payment_completing') and self.model._payment_completing:
            return
        
        # Check if user has paid anything
        if self.model.amount_received > 0:
            # Show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Cancel Payment?",
                f"You have paid P{self.model.amount_received:.2f}.\n\n"
                "Are you sure you want to cancel?\n"
                "There will be NO REFUNDS",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # User confirmed cancellation
                try:
                    # Temporarily disconnect to prevent navigation to print_options
                    self.model.go_back_requested.disconnect(self._go_back)
                    self.model.go_back()  # Adds money to inventory and cleans up
                    
                    # Clean up session directory since payment was cancelled
                    try:
                        self.main_app.usb_file_manager.cleanup_session_directory()
                        print("Session directory cleaned up after payment cancellation")
                    except Exception as cleanup_error:
                        print(f"Error cleaning up session directory on cancel: {cleanup_error}")
                    
                    # Clear USB file manager state (files_in_use tracking)
                    try:
                        self.main_app.usb_file_manager.files_in_use.clear()
                        self.main_app.usb_file_manager.operation_in_progress = False
                        print("USB file manager state cleared after cancellation")
                    except Exception as usb_cleanup_error:
                        print(f"Error clearing USB file manager state: {usb_cleanup_error}")
                    
                    # Clear main app print job state (if any exists)
                    try:
                        if hasattr(self.main_app, 'current_print_job'):
                            self.main_app.current_print_job = None
                        if hasattr(self.main_app, 'current_payment_info'):
                            self.main_app.current_payment_info = None
                        print("Main app print job state cleared after cancellation")
                    except Exception as app_cleanup_error:
                        print(f"Error clearing main app state: {app_cleanup_error}")
                    
                    # Navigate directly to idle screen
                    self.main_app.show_screen('idle')
                finally:
                    # Always reconnect signal, even if there's an error
                    try:
                        self.model.go_back_requested.connect(self._go_back)
                    except:
                        pass  # Already connected
        else:
            # No payment made, normal back behavior (to print options)
            self.model.go_back()
    
    def _go_back(self):
        if hasattr(self.main_app, 'show_screen'):
            self.main_app.show_screen('printing_options')
    
    # Enable payment mode and get payment data from print options screen
    def set_payment_data(self, payment_data):
        self.model.set_payment_data(payment_data)
        self.view.set_buttons_enabled(True)
    
    def on_enter(self):
        self.timeout_timer.start(300000)
        self.model.on_enter()
        self.view.set_buttons_enabled(True)
        # Reset button to normal state (in case coming back from cancellation)
        self.view.set_back_button_to_normal()
    
    def on_leave(self):
        self.timeout_timer.stop()
        self.model.on_leave()
    
    def go_back(self):
        self.model.go_back()
    
    def _on_timeout(self):
        # Safety check: Only navigate if we're still on this screen
        if self.main_app.stacked_widget.currentWidget() != self:
            return
        
        self.on_leave()
        self.main_app.show_screen('idle')
    
    def _reset_timeout(self):
        self.timeout_timer.stop()
        self.timeout_timer.start(300000)