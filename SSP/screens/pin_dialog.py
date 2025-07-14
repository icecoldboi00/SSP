from PyQt5.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QPushButton, QLabel, QDialogButtonBox)
from PyQt5.QtCore import Qt, QTimer

class PinDialog(QDialog):
    CORRECT_PIN = "1234"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Admin Access")
        self.setFixedSize(320, 450)
        self.current_pin = ""
        
        self.setup_ui()
        
    def setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1f1f38;
                border: 2px solid #4a4a6a;
            }
            QLabel {
                color: white;
                font-size: 18px;
            }
            QPushButton {
                background-color: #2a2a4a;
                color: white;
                font-size: 24px;
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 8px;
                min-height: 60px;
            }
            QPushButton:hover {
                background-color: #3a3a5a;
            }
            QPushButton:pressed {
                background-color: #1a1a3a;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- Display for the PIN ---
        self.pin_display = QLabel()
        self.pin_display.setAlignment(Qt.AlignCenter)
        self.pin_display.setMinimumHeight(50)
        self.pin_display.setStyleSheet("""
            QLabel {
                background-color: #101020;
                border: 1px solid #444;
                border-radius: 8px;
                font-size: 32px;
                padding: 5px;
            }
        """)
        
        # --- Status Label for messages ---
        self.status_label = QLabel("Enter PIN")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #aaa;")

        main_layout.addWidget(self.pin_display)
        main_layout.addWidget(self.status_label)

        # --- Keypad Layout ---
        keypad_layout = QGridLayout()
        keypad_layout.setSpacing(10)
        
        buttons = [
            '1', '2', '3',
            '4', '5', '6',
            '7', '8', '9',
            'C', '0', '✓'
        ]
        
        positions = [(i, j) for i in range(4) for j in range(3)]

        for position, value in zip(positions, buttons):
            button = QPushButton(value)
            if value.isdigit():
                button.clicked.connect(lambda _, v=value: self.on_number_click(v))
            elif value == 'C':
                button.setStyleSheet("background-color: #804d4d;") # Clear button style
                button.clicked.connect(self.clear_input)
            elif value == '✓':
                button.setStyleSheet("background-color: #4CAF50;") # Enter button style
                button.clicked.connect(self.check_pin)
            
            keypad_layout.addWidget(button, *position)

        main_layout.addLayout(keypad_layout)
        
    def on_number_click(self, number):
        """Appends a number to the current PIN."""
        if len(self.current_pin) < 8: # Limit PIN length
            self.current_pin += number
            self.update_display()
            
    def clear_input(self):
        """Clears the entire PIN."""
        self.current_pin = ""
        self.update_display()
        self.status_label.setText("Enter PIN")
        
    def check_pin(self):
        """Checks if the entered PIN is correct."""
        if self.current_pin == self.CORRECT_PIN:
            self.accept() # This closes the dialog and returns QDialog.Accepted
        else:
            self.status_label.setText("Incorrect PIN")
            # Briefly show error, then clear
            QTimer.singleShot(1000, self.clear_input)
            
    def update_display(self):
        """Updates the display to show asterisks instead of the PIN."""
        self.pin_display.setText('*' * len(self.current_pin))