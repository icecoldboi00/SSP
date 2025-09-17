# screens/print_options/controller.py

from PyQt5.QtWidgets import QWidget, QGridLayout, QMessageBox

from .model import PrintOptionsModel
from .view import PrintOptionsScreenView

class PrintOptionsController(QWidget):
    """Manages the Print Options screen's logic and UI."""
    
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        
        self.model = PrintOptionsModel()
        self.view = PrintOptionsScreenView()
        
        # Set the view's layout as this controller's layout
        self.setLayout(self.view.main_layout)
        
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect signals from the view to the model and vice-versa."""
        # --- View -> Controller ---
        self.view.back_button_clicked.connect(self._go_back)
        self.view.continue_button_clicked.connect(self._continue_to_payment)
        self.view.bw_mode_clicked.connect(self._set_bw_mode)
        self.view.color_mode_clicked.connect(self._set_color_mode)
        self.view.copies_decreased.connect(self._decrease_copies)
        self.view.copies_increased.connect(self._increase_copies)
        
        # --- Model -> View ---
        self.model.cost_updated.connect(self.view.update_cost_display)
        self.model.analysis_started.connect(self._on_analysis_started)
        self.model.analysis_completed.connect(self._on_analysis_completed)
        self.model.analysis_error.connect(self._on_analysis_error)
        self.model.show_message.connect(self._show_message)
    
    def _set_bw_mode(self):
        """Sets black and white mode."""
        self.model.set_color_mode("Black and White")
        self.view.set_bw_mode()
    
    def _set_color_mode(self):
        """Sets color mode."""
        self.model.set_color_mode("Color")
        self.view.set_color_mode()
    
    def _decrease_copies(self):
        """Decreases the number of copies."""
        self.model.change_copies(-1)
        self.view.update_copies_display(self.model.get_copies())
    
    def _increase_copies(self):
        """Increases the number of copies."""
        self.model.change_copies(1)
        self.view.update_copies_display(self.model.get_copies())
    
    def _on_analysis_started(self):
        """Handles when analysis starts."""
        self.view.set_continue_button_enabled(False)
        self.view.set_analysis_status(
            "Analyzing pages and calculating cost...",
            "This may take a moment for large documents..."
        )
    
    def _on_analysis_completed(self, results):
        """Handles when analysis is completed."""
        self.view.set_continue_button_enabled(True)
    
    def _on_analysis_error(self, error_message):
        """Handles analysis errors."""
        self.view.set_analysis_status("Error during analysis!", error_message)
        QMessageBox.critical(self, "Analysis Error", error_message)
    
    def _continue_to_payment(self):
        """Continues to the payment screen."""
        payment_data = self.model.get_payment_data()
        if not payment_data:
            QMessageBox.warning(self, "Please Wait", "Cost calculation is still in progress.")
            return
        
        self.main_app.payment_screen.set_payment_data(payment_data)
        self.main_app.show_screen('payment')
    
    def _go_back(self):
        """Goes back to the file browser screen."""
        print("Print options screen: going back to file browser")
        self.on_leave()
        self.main_app.show_screen('file_browser')
    
    def _show_message(self, title, text):
        """Shows a message to the user."""
        QMessageBox.information(self, title, text)
    
    # --- Public API for main_app ---
    
    def set_pdf_data(self, pdf_data, selected_pages):
        """Sets the PDF data and selected pages for printing."""
        self.model.set_pdf_data(pdf_data, selected_pages)
        self.view.update_copies_display(self.model.get_copies())
        self.view.set_bw_mode()
    
    def on_enter(self):
        """Called by main_app when this screen becomes active."""
        print("Print options screen entered")
        # Ensure analysis thread is not running from previous visits
        self.model.stop_analysis()
    
    def on_leave(self):
        """Called by main_app when leaving this screen."""
        print("Print options screen leaving")
        self.model.stop_analysis()
