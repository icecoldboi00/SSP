from PyQt5.QtWidgets import QWidget, QMessageBox
from PyQt5.QtCore import QTimer

from .model import PrintOptionsModel
from .view import PrintOptionsScreenView

class PrintOptionsController(QWidget):  
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        
        self.model = PrintOptionsModel()
        self.view = PrintOptionsScreenView()
        
        # Setup timeout timer (1 minute = 60000ms)
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._on_timeout)
        
        # Set the view's layout as this controller's layout
        self.setLayout(self.view.main_layout)
        
        self._connect_signals()

    def _connect_signals(self):
        self.view.back_button_clicked.connect(self._go_back)
        self.view.continue_button_clicked.connect(self._continue_to_payment)
        self.view.bw_mode_clicked.connect(self._set_bw_mode)
        self.view.color_mode_clicked.connect(self._set_color_mode)
        self.view.copies_decreased.connect(self._decrease_copies)
        self.view.copies_increased.connect(self._increase_copies)
        
        # For for resetting timers every click
        self.view.back_button_clicked.connect(self._reset_timeout)
        self.view.continue_button_clicked.connect(self._reset_timeout)
        self.view.bw_mode_clicked.connect(self._reset_timeout)
        self.view.color_mode_clicked.connect(self._reset_timeout)
        self.view.copies_decreased.connect(self._reset_timeout)
        self.view.copies_increased.connect(self._reset_timeout)
        
        self.model.cost_updated.connect(self.view.update_cost_display)
        self.model.analysis_started.connect(self._on_analysis_started)
        self.model.analysis_completed.connect(self._on_analysis_completed)
        self.model.analysis_error.connect(self._on_analysis_error)
        self.model.show_message.connect(self._show_message)
    
    def _set_bw_mode(self):
        self.model.set_color_mode("Black and White")
        self.view.set_bw_mode()
        self._check_paper_availability()
    
    def _set_color_mode(self):
        self.model.set_color_mode("Color")
        self.view.set_color_mode()
        self._check_paper_availability()
    
    def _decrease_copies(self):
        self.model.change_copies(-1)
        self.view.update_copies_display(self.model.get_copies())
        self._check_paper_availability()
    
    def _increase_copies(self):
        self.model.change_copies(1)
        self.view.update_copies_display(self.model.get_copies())
        self._check_paper_availability()
    
    def _on_analysis_started(self):
        self.view.set_continue_button_enabled(False)
        self.view.set_analysis_status(
            "Analyzing pages and calculating cost...",
            "This may take a moment for large documents..."
        )
    
    def _on_analysis_completed(self, results):
        print("Analysis completed")
        self.view.set_continue_button_enabled(True)
        # Check paper availability after analysis is complete with a small delay
        QTimer.singleShot(100, self._check_paper_availability)
    
    def _on_analysis_error(self, error_message):
        self.view.set_analysis_status("Error during analysis!", error_message)
        QMessageBox.critical(self, "Analysis Error", error_message)
    
    def _continue_to_payment(self):
        payment_data = self.model.get_payment_data()
        if not payment_data:
            QMessageBox.warning(self, "Please Wait", "Cost calculation is still in progress.")
            return
        
        # Check paper availability before proceeding to payment
        total_pages = len(payment_data['selected_pages']) * payment_data['copies']
        admin_screen = self.main_app.admin_screen
        available_paper = admin_screen.get_paper_count()
        
        if available_paper < total_pages:
            # Disable continue button and show warning
            self.view.set_continue_button_enabled(False)
            self.view.show_paper_warning(available_paper, total_pages)
            return
        
        self.main_app.payment_screen.set_payment_data(payment_data) # Pass to controller
        self.main_app.show_screen('payment')
    
    def _go_back(self):
        print("Print options screen: going back to file browser")
        self.on_leave()
        self.main_app.show_screen('file_browser')
    
    def _show_message(self, title, text):
        QMessageBox.information(self, title, text)
    
    def set_pdf_data(self, pdf_data, selected_pages):
        self.model.set_pdf_data(pdf_data, selected_pages)
        self.view.update_copies_display(self.model.get_copies())
        self.view.set_bw_mode()
        # Clear any existing warnings when setting new PDF data
        self.view.clear_paper_warning()
        # Check paper availability immediately after setting PDF data
        QTimer.singleShot(100, self._check_paper_availability)

        
    def _check_paper_availability(self):
        print("Paper availability check")
        # Get current state from model even if payment data isn't ready
        selected_pages = getattr(self.model, 'selected_pages', None)
        copies = getattr(self.model, '_copies', 1)
        
        if not selected_pages:
            print("No selected pages available yet")
            return
        
        total_pages = len(selected_pages) * copies
        admin_screen = self.main_app.admin_screen
        available_paper = admin_screen.get_paper_count()
        
        if available_paper < total_pages:
            # Show warning and disable continue button
            self.view.show_paper_warning(available_paper, total_pages)
        else:
            self.view.clear_paper_warning()
    
    def on_enter(self):
        print("Print options screen entered")
        # Ensure analysis thread is not running from previous visits
        self.model.stop_analysis()
        
        # Clear any existing paper warnings first
        self.view.clear_paper_warning()
        
        # Delay paper availability check slightly to ensure admin_screen is ready
        QTimer.singleShot(100, self._check_paper_availability)
        
        # Start timeout timer (5 minutes)
        self.timeout_timer.start(300000)
        print("Screen timeout started 5")
    
    def on_leave(self):
        print("Print options screen leaving")
        self.model.stop_analysis()
        # Stop timeout timer
        self.timeout_timer.stop()
    
    def _on_timeout(self):
        # Safety check: Only navigate if we're still on this screen
        if self.main_app.stacked_widget.currentWidget() != self:
            print("Print options timeout fired but we're not on this screen anymore - ignoring")
            return
        
        print("Screen timeout, returning to idle screen")
        self.main_app.show_screen('idle')
    
    def _reset_timeout(self):
        self.timeout_timer.stop()
        self.timeout_timer.start(300000) # ms
        print("Timeout reset")
