# --- START OF FILE admin_screen.py ---

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                            QHBoxLayout, QProgressBar, QFrame)
from PyQt5.QtCore import Qt

class AdminScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.paper_count = 50  # Starting with 50 sheets
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("background-color: #1f1f38;")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        
        title = QLabel("Admin Panel")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 36px;
                font-weight: bold;
            }
        """)
        
        # Replace placeholder with actual admin controls
        admin_container = QFrame()
        admin_container.setStyleSheet("""
            QFrame {
                background-color: #2c2c4f;
                border-radius: 15px;
                padding: 20px;
            }
        """)
        
        admin_layout = QVBoxLayout()
        
        # Paper Level Section
        paper_section = QFrame()
        paper_layout = QHBoxLayout()
        
        paper_label = QLabel("Paper Count:")
        paper_label.setStyleSheet("color: white; font-size: 16px;")
        
        self.paper_count_display = QLabel(f"{self.paper_count} sheets")
        self.paper_count_display.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                padding: 5px 10px;
                background-color: #1f1f38;
                border: 2px solid #4a4a6b;
                border-radius: 5px;
                min-width: 100px;
                text-align: center;
            }
        """)
        
        reset_paper_btn = QPushButton("Reset Paper (50 sheets)")
        reset_paper_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                border: none;
                border-radius: 5px;
                padding: 8px 15px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        reset_paper_btn.clicked.connect(self.reset_paper_count)
        
        paper_layout.addWidget(paper_label)
        paper_layout.addWidget(self.paper_count_display)
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
        
        # Transaction History Button
        transaction_btn = QPushButton("View Transaction History")
        transaction_btn.setStyleSheet("""
            QPushButton {
                background-color: #3f51b5;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 15px;
            }
            QPushButton:hover {
                background-color: #303f9f;
            }
        """)
        transaction_btn.clicked.connect(self.show_transaction_history)
        
        # Add all sections to admin layout
        admin_layout.addWidget(paper_section)
        admin_layout.addWidget(ink_section)
        admin_layout.addWidget(transaction_btn)
        admin_container.setLayout(admin_layout)
        
        # Main Layout
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addWidget(admin_container)
        layout.addStretch(2)
        
        back_button = QPushButton("← Back to Main Screen")
        back_button.setMinimumHeight(50)
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #804d4d;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #905d5d;
            }
        """)
        back_button.clicked.connect(self.go_back)
        
        layout.addWidget(back_button)
        
        self.setLayout(layout)
        
    def go_back(self):
        """Navigate back to the idle screen"""
        self.main_app.show_screen('idle')

    def on_enter(self):
        """Called when this screen becomes active."""
        print("DEBUG: Admin screen entered.")
        
    def on_leave(self):
        """Called when this screen is left."""
        print("DEBUG: Admin screen left.")
        
    def reset_paper_count(self):
        """Reset paper count to 50 sheets"""
        self.paper_count = 50
        self.update_paper_display()
        print("DEBUG: Paper count reset to 50 sheets")

    def update_paper_count(self, pages_to_print):
        """Update paper count based on pages being printed"""
        if self.paper_count >= pages_to_print:
            self.paper_count = max(0, self.paper_count - pages_to_print)
            self.update_paper_display()
            print(f"DEBUG: Paper count updated to {self.paper_count} sheets")
            return True
        return False

    def update_paper_display(self):
        """Update the paper count display and styling"""
        self.paper_count_display.setText(f"{self.paper_count} sheets")
        
        if self.paper_count <= 10:
            color = "#dc3545"  # Red for low paper
        elif self.paper_count <= 20:
            color = "#ffc107"  # Yellow for warning
        else:
            color = "#4CAF50"  # Green for good
            
        self.paper_count_display.setStyleSheet(f"""
            QLabel {{
                color: white;
                font-size: 16px;
                padding: 5px 10px;
                background-color: {color};
                border: 2px solid #4a4a6b;
                border-radius: 5px;
                min-width: 100px;
                text-align: center;
            }}
        """)

    def get_paper_count(self):
        """Return current paper count"""
        return self.paper_count

    def show_transaction_history(self):
        """Placeholder for transaction history functionality"""
        print("DEBUG: Transaction history button clicked")
        # To be implemented later