# screens/print_options_screen.py

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QComboBox, QFrame, QGridLayout, QMessageBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

# ## FIX: Using the non-standard name 'Print_Options_Screen' to match your
# ## original definition and the import in main_app.py.
# ## Standard Python would be 'PrintOptionsScreen'.
class Print_Options_Screen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.selected_pdf = None
        self.selected_pages = None
        self.color_mode = 'bw'
        self.copies = 1
        self.setup_ui()

    def setup_ui(self):
        # ... (Your setup_ui code is perfect, no changes needed) ...
        # The "Continue to Payment" button here is correct.
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Printing Options")
        title.setStyleSheet("color: white; font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title)

        options_frame = QFrame()
        options_frame.setStyleSheet("background-color: #2a2a4a; border-radius: 10px; padding: 20px;")
        options_layout = QGridLayout()
        
        color_label = QLabel("Color Mode:")
        color_label.setStyleSheet("color: white; font-size: 16px;")
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Black & White", "Color"])
        self.color_combo.setStyleSheet("QComboBox { background-color: #333366; color: white; padding: 8px; border: 1px solid #444; border-radius: 4px; min-width: 150px; }")
        self.color_combo.currentTextChanged.connect(self.update_cost)
        
        copies_label = QLabel("Number of Copies:")
        copies_label.setStyleSheet("color: white; font-size: 16px;")
        self.copies_spin = QSpinBox()
        self.copies_spin.setMinimum(1)
        self.copies_spin.setMaximum(99)
        self.copies_spin.setStyleSheet("QSpinBox { background-color: #333366; color: white; padding: 8px; border: 1px solid #444; border-radius: 4px; min-width: 150px; }")
        self.copies_spin.valueChanged.connect(self.update_cost)

        options_layout.addWidget(color_label, 0, 0)
        options_layout.addWidget(self.color_combo, 0, 1)
        options_layout.addWidget(copies_label, 1, 0)
        options_layout.addWidget(self.copies_spin, 1, 1)
        options_frame.setLayout(options_layout)
        layout.addWidget(options_frame)

        self.cost_label = QLabel()
        self.cost_label.setStyleSheet("color: #33cc33; font-size: 20px; font-weight: bold; margin: 20px 0;")
        layout.addWidget(self.cost_label)

        buttons_layout = QHBoxLayout()
        back_btn = QPushButton("← Back to File Browser")
        back_btn.clicked.connect(self.go_back)
        back_btn.setStyleSheet("QPushButton { background-color: #4d4d80; color: white; padding: 12px 24px; border: none; border-radius: 4px; font-size: 16px; } QPushButton:hover { background-color: #5d5d90; }")
        continue_btn = QPushButton("Continue to Payment →")
        continue_btn.clicked.connect(self.continue_to_payment)
        continue_btn.setStyleSheet("QPushButton { background-color: #33cc33; color: white; padding: 12px 24px; border: none; border-radius: 4px; font-size: 16px; } QPushButton:hover { background-color: #2eb82e; }")
        buttons_layout.addWidget(back_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(continue_btn)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    # This method is called by the FileBrowserScreen
    def set_pdf_data(self, pdf_data, selected_pages):
        self.selected_pdf = pdf_data
        self.selected_pages = selected_pages
        # Reset options to default every time new data is set
        self.copies_spin.setValue(1)
        self.color_combo.setCurrentIndex(0)
        self.update_cost()

    def update_cost(self):
        if not self.selected_pdf or not self.selected_pages:
            return
        per_page_cost = 8.00 if self.color_combo.currentText() == "Color" else 4.00
        num_pages_to_print = len(self.selected_pages)
        num_copies = self.copies_spin.value()
        total_cost = num_pages_to_print * num_copies * per_page_cost
        self.cost_label.setText(f"Total Cost: ₱{total_cost:.2f}")

    def go_back(self):
        self.main_app.show_screen('file_browser')

    # This method correctly transitions to the payment screen
    def continue_to_payment(self):
        if not self.selected_pdf or not self.selected_pages:
            QMessageBox.warning(self, "Error", "No PDF data available.")
            return

        per_page_cost = 8.00 if self.color_combo.currentText() == "Color" else 4.00
        total_cost = len(self.selected_pages) * self.copies_spin.value() * per_page_cost
        payment_data = {
            'pdf_data': self.selected_pdf,
            'selected_pages': self.selected_pages,
            'color_mode': self.color_combo.currentText(),
            'copies': self.copies_spin.value(),
            'total_cost': total_cost,
            'price_per_page': per_page_cost
        }

        # Get the existing payment screen and set its data
        self.main_app.payment_screen.set_payment_data(payment_data)
        self.main_app.show_screen('payment')