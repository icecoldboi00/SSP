from PyQt5.QtWidgets import QWidget
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
        self.view.back_button_clicked.connect(self.model.go_back)
    
        self.model.payment_data_updated.connect(self.view.update_payment_data)
        self.model.payment_status_updated.connect(self.view.update_payment_status)
        self.model.amount_received_updated.connect(self.view.update_amount_received)
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
    
    def _go_back(self):
        if hasattr(self.main_app, 'show_screen'):
            self.main_app.show_screen('printing_options')
    
    # Enable payment mode and get payment data from print options screen
    def set_payment_data(self, payment_data):
        self.model.set_payment_data(payment_data)
        self.view.set_buttons_enabled(True)
        
        if hasattr(self.model, 'gpio_thread') and self.model.gpio_thread:
            self.model.enable_payment_mode()
    
    def on_enter(self):
        self.timeout_timer.start(300000)
        self.model.on_enter()
        self.view.set_buttons_enabled(True)
    
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