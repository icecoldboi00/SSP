# screens/data_viewer/view.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QTabWidget, 
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt5.QtCore import Qt, pyqtSignal

class DataViewerScreenView(QWidget):
    """The user interface for the Data Viewer Screen. Contains no logic."""
    back_clicked = pyqtSignal()
    refresh_transactions_clicked = pyqtSignal()
    refresh_cash_inventory_clicked = pyqtSignal()
    refresh_error_log_clicked = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background-color: #0f1f00;")
        self.setup_ui()
    
    def setup_ui(self):
        """Sets up the user interface components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 30, 50, 30)
        layout.setSpacing(20)

        # --- Title ---
        title = QLabel("System Data Logs")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; font-size: 48px; font-weight: bold; text-shadow: 2px 2px 4px #000000;")

        # --- Tab Widget ---
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(self.get_tab_widget_style())

        # Add tabs for different data views
        self.tab_widget.addTab(self.create_transactions_tab(), "Transactions")
        self.tab_widget.addTab(self.create_cash_inventory_tab(), "Cash Inventory")
        self.tab_widget.addTab(self.create_error_log_tab(), "Error Log")

        # --- Back Button ---
        self.back_button = QPushButton("← Back to Admin Screen")
        self.back_button.setMinimumHeight(60)
        self.back_button.setCursor(Qt.PointingHandCursor)
        self.back_button.setStyleSheet(self.get_back_button_style())
        self.back_button.clicked.connect(self.back_clicked.emit)

        layout.addWidget(title)
        layout.addWidget(self.tab_widget, 1)  # Add stretch factor
        layout.addWidget(self.back_button)
        self.setLayout(layout)
    
    def create_tab_widget(self, table_widget, refresh_button):
        """Generic helper to create a tab with a table and a refresh button."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        layout.addWidget(table_widget)
        layout.addWidget(refresh_button, 0, Qt.AlignRight)
        
        return widget

    def create_transactions_tab(self):
        """Creates the transactions tab."""
        self.transactions_table = QTableWidget()
        self.transactions_table.setStyleSheet(self.get_table_style())
        
        self.refresh_transactions_btn = QPushButton("Refresh Data")
        self.refresh_transactions_btn.setStyleSheet(self.get_button_style())
        self.refresh_transactions_btn.clicked.connect(self.refresh_transactions_clicked.emit)
        
        return self.create_tab_widget(self.transactions_table, self.refresh_transactions_btn)

    def create_cash_inventory_tab(self):
        """Creates the cash inventory tab."""
        self.cash_inventory_table = QTableWidget()
        self.cash_inventory_table.setStyleSheet(self.get_table_style())
        
        self.refresh_cash_inventory_btn = QPushButton("Refresh Data")
        self.refresh_cash_inventory_btn.setStyleSheet(self.get_button_style())
        self.refresh_cash_inventory_btn.clicked.connect(self.refresh_cash_inventory_clicked.emit)
        
        return self.create_tab_widget(self.cash_inventory_table, self.refresh_cash_inventory_btn)
        
    def create_error_log_tab(self):
        """Creates the error log tab."""
        self.error_log_table = QTableWidget()
        self.error_log_table.setStyleSheet(self.get_table_style())
        
        self.refresh_error_log_btn = QPushButton("Refresh Data")
        self.refresh_error_log_btn.setStyleSheet(self.get_button_style())
        self.refresh_error_log_btn.clicked.connect(self.refresh_error_log_clicked.emit)
        
        return self.create_tab_widget(self.error_log_table, self.refresh_error_log_btn)
    
    def update_transactions_table(self, transactions):
        """Updates the transactions table with new data."""
        self.transactions_table.clear()
        self.transactions_table.setColumnCount(9)
        self.transactions_table.setHorizontalHeaderLabels([
            "ID", "Date/Time", "File Name", "Pages", "Copies",
            "Color Mode", "Total Cost", "Amount Paid", "Status"
        ])
        self.transactions_table.setRowCount(len(transactions))
        
        for i, trans in enumerate(transactions):
            self.transactions_table.setItem(i, 0, QTableWidgetItem(str(trans['id'])))
            self.transactions_table.setItem(i, 1, QTableWidgetItem(str(trans['timestamp'])))
            self.transactions_table.setItem(i, 2, QTableWidgetItem(trans['file_name']))
            self.transactions_table.setItem(i, 3, QTableWidgetItem(str(trans['pages'])))
            self.transactions_table.setItem(i, 4, QTableWidgetItem(str(trans['copies'])))
            self.transactions_table.setItem(i, 5, QTableWidgetItem(trans['color_mode']))
            self.transactions_table.setItem(i, 6, QTableWidgetItem(f"₱{trans['total_cost']:.2f}"))
            self.transactions_table.setItem(i, 7, QTableWidgetItem(f"₱{trans['amount_paid']:.2f}"))
            self.transactions_table.setItem(i, 8, QTableWidgetItem(trans['status']))
        
        self.transactions_table.resizeColumnsToContents()
    
    def update_cash_inventory_table(self, inventory):
        """Updates the cash inventory table with new data."""
        self.cash_inventory_table.clear()
        self.cash_inventory_table.setColumnCount(4)
        self.cash_inventory_table.setHorizontalHeaderLabels(["Denomination", "Count", "Type", "Last Updated"])
        self.cash_inventory_table.setRowCount(len(inventory))
        
        for i, item in enumerate(inventory):
            self.cash_inventory_table.setItem(i, 0, QTableWidgetItem(f"₱{item['denomination']}"))
            self.cash_inventory_table.setItem(i, 1, QTableWidgetItem(str(item['count'])))
            self.cash_inventory_table.setItem(i, 2, QTableWidgetItem(item['type']))
            self.cash_inventory_table.setItem(i, 3, QTableWidgetItem(str(item['last_updated'])))
        
        self.cash_inventory_table.resizeColumnsToContents()
    
    def update_error_log_table(self, errors):
        """Updates the error log table with new data."""
        self.error_log_table.clear()
        self.error_log_table.setColumnCount(4)
        self.error_log_table.setHorizontalHeaderLabels(["Date/Time", "Error Type", "Message", "Context"])
        self.error_log_table.setRowCount(len(errors))
        
        for i, error in enumerate(errors):
            self.error_log_table.setItem(i, 0, QTableWidgetItem(str(error['timestamp'])))
            self.error_log_table.setItem(i, 1, QTableWidgetItem(error['error_type']))
            self.error_log_table.setItem(i, 2, QTableWidgetItem(error['message']))
            self.error_log_table.setItem(i, 3, QTableWidgetItem(error['context']))
        
        self.error_log_table.resizeColumnsToContents()
    
    def get_tab_widget_style(self):
        """Returns the style for the tab widget."""
        return """
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
        """

    def get_table_style(self):
        """Returns the style for tables."""
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
        """Returns the style for buttons."""
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

    def get_back_button_style(self):
        """Returns the style for the back button."""
        return """
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
        """
