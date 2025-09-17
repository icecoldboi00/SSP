# screens/data_viewer/controller.py

from PyQt5.QtWidgets import QWidget, QGridLayout, QMessageBox

from .model import DataViewerModel
from .view import DataViewerScreenView

class DataViewerController(QWidget):
    """Manages the Data Viewer screen's logic and UI."""
    
    def __init__(self, main_app, db_manager, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        
        self.model = DataViewerModel(db_manager)
        self.view = DataViewerScreenView()
        
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, 0, 0)
        
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect signals from the view to the model and vice-versa."""
        # --- View -> Controller ---
        self.view.back_clicked.connect(self._go_back)
        self.view.refresh_transactions_clicked.connect(self.model.load_transactions)
        self.view.refresh_cash_inventory_clicked.connect(self.model.load_cash_inventory)
        self.view.refresh_error_log_clicked.connect(self.model.load_error_log)
        
        # --- Model -> View ---
        self.model.transactions_loaded.connect(self.view.update_transactions_table)
        self.model.cash_inventory_loaded.connect(self.view.update_cash_inventory_table)
        self.model.error_log_loaded.connect(self.view.update_error_log_table)
        self.model.show_message.connect(self._show_message)
    
    def _go_back(self):
        """Navigates back to the admin screen."""
        self.main_app.show_screen('admin')
    
    def _show_message(self, title, text):
        """Shows a message to the user."""
        QMessageBox.warning(self, title, text)
    
    # --- Public API for main_app ---
    
    def on_enter(self):
        """Called by main_app when this screen becomes active."""
        print("Data viewer screen entered. Loading all data.")
        self.model.refresh_all_data()
    
    def on_leave(self):
        """Called by main_app when leaving this screen."""
        print("Data viewer screen left.")
