# screens/admin_screen.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame,
    QDialog, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt
from database.db_manager import DatabaseManager

# --- Data Viewer Dialog Class ---
# This class creates a pop-up window with tabs to show database information.
class DataViewerDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Data Viewer")
        self.setMinimumSize(800, 600)
        self.setStyleSheet("background-color: #2c2c4f;")

        layout = QVBoxLayout(self)

        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #4a4a6b; }
            QTabBar::tab {
                background-color: #1f1f38;
                color: white;
                padding: 10px 20px;
                margin: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                border: 1px solid #4a4a6b;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #3f51b5;
                color: white;
            }
        """)

        # Add tabs for different data views
        tab_widget.addTab(self.create_transactions_tab(), "Transactions")
        tab_widget.addTab(self.create_cash_inventory_tab(), "Cash Inventory")
        tab_widget.addTab(self.create_error_log_tab(), "Error Log")

        layout.addWidget(tab_widget)
        self.setLayout(layout)

    def create_tab_widget(self, refresh_function):
        """Generic helper to create a tab with a table and a refresh button."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        table = QTableWidget()
        table.setStyleSheet(self.get_table_style())
        
        refresh_btn = QPushButton("Refresh Data")
        refresh_btn.setStyleSheet(self.get_button_style())
        refresh_btn.clicked.connect(lambda: refresh_function(table))

        layout.addWidget(table)
        layout.addWidget(refresh_btn, 0, Qt.AlignRight)
        
        # Initial data load
        refresh_function(table)
        return widget

    def create_transactions_tab(self):
        return self.create_tab_widget(self.refresh_transactions_table)

    def create_cash_inventory_tab(self):
        return self.create_tab_widget(self.refresh_cash_inventory_table)
        
    def create_error_log_tab(self):
        return self.create_tab_widget(self.refresh_error_log_table)

    def refresh_transactions_table(self, table: QTableWidget):
        table.clear()
        table.setColumnCount(9)
        table.setHorizontalHeaderLabels([
            "ID", "Date/Time", "File Name", "Pages", "Copies",
            "Color Mode", "Total Cost", "Amount Paid", "Status"
        ])
        transactions = self.db_manager.get_transaction_history()
        table.setRowCount(len(transactions))
        for i, trans in enumerate(transactions): # Already sorted by DB query
            table.setItem(i, 0, QTableWidgetItem(str(trans['id'])))
            table.setItem(i, 1, QTableWidgetItem(str(trans['timestamp'])))
            table.setItem(i, 2, QTableWidgetItem(trans['file_name']))
            table.setItem(i, 3, QTableWidgetItem(str(trans['pages'])))
            table.setItem(i, 4, QTableWidgetItem(str(trans['copies'])))
            table.setItem(i, 5, QTableWidgetItem(trans['color_mode']))
            table.setItem(i, 6, QTableWidgetItem(f"₱{trans['total_cost']:.2f}"))
            table.setItem(i, 7, QTableWidgetItem(f"₱{trans['amount_paid']:.2f}"))
            table.setItem(i, 8, QTableWidgetItem(trans['status']))
        table.resizeColumnsToContents()

    def refresh_cash_inventory_table(self, table: QTableWidget):
        table.clear()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Denomination", "Count", "Type", "Last Updated"])
        inventory = self.db_manager.get_cash_inventory()
        table.setRowCount(len(inventory))
        for i, item in enumerate(inventory):
            table.setItem(i, 0, QTableWidgetItem(f"₱{item['denomination']}"))
            table.setItem(i, 1, QTableWidgetItem(str(item['count'])))
            table.setItem(i, 2, QTableWidgetItem(item['type']))
            table.setItem(i, 3, QTableWidgetItem(str(item['last_updated'])))
        table.resizeColumnsToContents()

    def refresh_error_log_table(self, table: QTableWidget):
        table.clear()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Date/Time", "Error Type", "Message", "Context"])
        errors = self.db_manager.get_error_log()
        table.setRowCount(len(errors))
        for i, error in enumerate(errors): # Already sorted by DB query
            table.setItem(i, 0, QTableWidgetItem(str(error['timestamp'])))
            table.setItem(i, 1, QTableWidgetItem(error['error_type']))
            table.setItem(i, 2, QTableWidgetItem(error['message']))
            table.setItem(i, 3, QTableWidgetItem(error['context']))
        table.resizeColumnsToContents()

    def get_table_style(self):
        return """
            QTableWidget { background-color: #1f1f38; color: white; gridline-color: #3f3f5f; border: none; }
            QHeaderView::section { background-color: #3f51b5; color: white; padding: 5px; border: 1px solid #3f3f5f; }
            QTableWidget::item { border-bottom: 1px solid #3f3f5f; padding: 5px; }
        """

    def get_button_style(self):
        return """
            QPushButton { background-color: #4CAF50; color: white; padding: 8px 15px; border-radius: 5px; font-size: 14px; border: none; }
            QPushButton:hover { background-color: #45a049; }
        """


class AdminScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.db_manager = DatabaseManager()
        self.paper_count = self.load_paper_count_from_db()
        self.setup_ui()
        self.update_paper_display() # Update display on first load

    def setup_ui(self):
        self.setStyleSheet("background-color: #1f1f38;")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        title = QLabel("Admin Panel")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("QLabel { color: white; font-size: 36px; font-weight: bold; }")
        
        admin_container = QFrame()
        admin_container.setStyleSheet("QFrame { background-color: #2c2c4f; border-radius: 15px; padding: 20px; }")
        
        admin_layout = QVBoxLayout()
        
        # Paper Level Section
        paper_section = QFrame()
        paper_layout = QHBoxLayout()
        
        paper_label = QLabel("Paper Count:")
        paper_label.setStyleSheet("color: white; font-size: 16px;")
        
        self.paper_count_display = QLabel(f"{self.paper_count} sheets")
        
        reset_paper_btn = QPushButton("Reset Paper (500 sheets)") # CORRECTED
        reset_paper_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-size: 14px; border: none; border-radius: 5px; padding: 8px 15px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        reset_paper_btn.clicked.connect(self.reset_paper_count)
        
        paper_layout.addWidget(paper_label)
        paper_layout.addWidget(self.paper_count_display)
        paper_layout.addStretch()
        paper_layout.addWidget(reset_paper_btn)
        paper_section.setLayout(paper_layout)
        
        # Ink Level Section (Placeholder)
        ink_section = QFrame()
        ink_layout = QHBoxLayout()
        
        ink_label = QLabel("Ink Level:")
        ink_label.setStyleSheet("color: white; font-size: 16px;")
        ink_placeholder = QLabel("Coming Soon")
        ink_placeholder.setStyleSheet("color: #cccccc; font-style: italic;")
        
        ink_layout.addWidget(ink_label)
        ink_layout.addWidget(ink_placeholder)
        ink_section.setLayout(ink_layout)
        
        # Data Viewer Button
        transaction_btn = QPushButton("View System Data")
        transaction_btn.setStyleSheet("""
            QPushButton { background-color: #3f51b5; color: white; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; padding: 15px; }
            QPushButton:hover { background-color: #303f9f; }
        """)
        transaction_btn.clicked.connect(self.show_data_viewer)
        
        admin_layout.addWidget(paper_section)
        admin_layout.addWidget(ink_section)
        admin_layout.addSpacing(20)
        admin_layout.addWidget(transaction_btn)
        admin_container.setLayout(admin_layout)
        
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(admin_container)
        layout.addStretch(2)
        
        back_button = QPushButton("← Back to Main Screen")
        back_button.setMinimumHeight(50)
        back_button.setStyleSheet("""
            QPushButton { background-color: #804d4d; color: white; font-size: 16px; font-weight: bold; border: none; border-radius: 8px; padding: 10px; }
            QPushButton:hover { background-color: #905d5d; }
        """)
        back_button.clicked.connect(self.go_back)
        
        layout.addWidget(back_button)
        self.setLayout(layout)
        
    def go_back(self):
        self.main_app.show_screen('idle')

    def on_enter(self):
        """Called when this screen becomes active. Reloads data from DB."""
        print("DEBUG: Admin screen entered. Refreshing data.")
        self.paper_count = self.load_paper_count_from_db()
        self.update_paper_display()
        
    def load_paper_count_from_db(self):
        """Loads the current paper count from the database."""
        return self.db_manager.get_setting('paper_count', default=500)

    def reset_paper_count(self):
        """Reset paper count to 500 sheets and save to DB."""
        self.paper_count = 500
        self.db_manager.update_setting('paper_count', self.paper_count)
        self.update_paper_display()
        print("DEBUG: Paper count reset to 500 sheets")

    def update_paper_count(self, pages_to_print):
        """Update paper count and save to DB. Returns True if enough paper."""
        if self.paper_count >= pages_to_print:
            self.paper_count = max(0, self.paper_count - pages_to_print)
            self.db_manager.update_setting('paper_count', self.paper_count)
            self.update_paper_display()
            print(f"DEBUG: Paper count updated to {self.paper_count} sheets")
            return True
        print(f"ERROR: Not enough paper. Required: {pages_to_print}, Available: {self.paper_count}")
        return False

    def update_paper_display(self):
        """Update the paper count label and its color based on the amount."""
        self.paper_count_display.setText(f"{self.paper_count} sheets")
        
        if self.paper_count <= 20:
            color = "#dc3545"  # Red for critical
        elif self.paper_count <= 50:
            color = "#ffc107"  # Yellow for warning
        else:
            color = "#28a745"  # Green for good
            
        self.paper_count_display.setStyleSheet(f"""
            QLabel {{
                color: white; font-size: 16px; padding: 5px 10px;
                background-color: {color}; border: 2px solid #4a4a6b;
                border-radius: 5px; min-width: 120px; qproperty-alignment: 'AlignCenter';
            }}
        """)

    def get_paper_count(self):
        return self.paper_count

    def show_data_viewer(self):
        """Create and show the data viewer dialog window."""
        print("DEBUG: System data viewer button clicked")
        dialog = DataViewerDialog(self.db_manager, self)
        dialog.exec_()