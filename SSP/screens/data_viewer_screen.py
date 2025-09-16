# screens/data_viewer_screen.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QTabWidget, 
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt

class DataViewerScreen(QWidget):
    def __init__(self, main_app, db_manager, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        self.db_manager = db_manager
        self.setStyleSheet("background-color: #0f1f00;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.setSpacing(20)

        # --- Title ---
        title = QLabel("System Data Logs")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-size: 48px; font-weight: bold; text-shadow: 2px 2px 4px #000000;")

        tab_widget = QTabWidget()
        tab_widget.setStyleSheet("""
            QTabWidget::pane { 
                border: 1px solid #2a5d1a; 
            }
            QTabBar::tab {
                background-color: #15300a;
                color: white;
                padding: 10px 20px;
                margin: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
                border: 1px solid #2a5d1a;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #1e440a;
                color: white;
            }
        """)

        # Add tabs for different data views
        tab_widget.addTab(self.create_transactions_tab(), "Transactions")
        tab_widget.addTab(self.create_cash_inventory_tab(), "Cash Inventory")
        tab_widget.addTab(self.create_error_log_tab(), "Error Log")

        # --- Back Button ---
        back_button = QPushButton("← Back to Admin Screen")
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

        layout.addWidget(title)
        layout.addWidget(tab_widget, 1) # Add stretch factor
        layout.addWidget(back_button)
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
            QTableWidget { 
                background-color: #f5f5dc; /* Beige background */
                color: black; /* Black text for readability */
                gridline-color: #d3d3d3; /* Light gray gridlines */
                border: none; 
            }
            QHeaderView::section { 
                background-color: #1e440a; /* Dark green header */
                color: white; 
                padding: 5px; 
                border: 1px solid #2a5d1a; 
            }
            QTableWidget::item { 
                border-bottom: 1px solid #dcdcdc; /* Slightly darker gray for item borders */
                padding: 5px; 
            }
        """

    def get_button_style(self):
        return """
            QPushButton { 
                background-color: #1e440a; /* Green theme button */
                color: white; 
                padding: 8px 15px; 
                border-radius: 5px; 
                font-size: 14px; 
                border: none; 
            }
            QPushButton:hover { 
                background-color: #2a5d1a; /* Lighter green on hover */
            }
        """
    
    def go_back(self):
        """Navigates back to the admin screen."""
        self.main_app.show_screen('admin')