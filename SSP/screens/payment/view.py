import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QMessageBox, QScrollArea, QStackedLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QPixmap

try:
    import pigpio
    PAYMENT_GPIO_AVAILABLE = True
except ImportError:
    PAYMENT_GPIO_AVAILABLE = False

class PaymentScreenView(QWidget):
    """View for the Payment screen - handles UI components and presentation."""
    
    # Signals for user interactions
    back_button_clicked = pyqtSignal()
    payment_mode_toggle_clicked = pyqtSignal()  # Toggle between enable/disable
    payment_button_clicked = pyqtSignal()
    simulation_coin_clicked = pyqtSignal(int)  # coin_value
    simulation_bill_clicked = pyqtSignal(int)  # bill_value
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Sets up the user interface for the screen."""
        stacked_layout = QStackedLayout()
        stacked_layout.setContentsMargins(0, 0, 0, 0)
        stacked_layout.setStackingMode(QStackedLayout.StackAll)
        
        # Background
        self.background_label = QLabel()
        self._load_background_image()

        # Foreground
        foreground_widget = QWidget()
        foreground_widget.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(foreground_widget)
        main_layout.setContentsMargins(30, 20, 30, 30)
        main_layout.setSpacing(10)
        main_layout.addStretch(1)

        # Summary label
        self.summary_label = QLabel("Print Job Summary")
        self.summary_label.setStyleSheet(
            "QLabel { color: #36454F; font-size: 16px; font-weight: normal; margin-bottom: 15px; line-height: 1.5; "
            "background-color: transparent; padding: 10px; border-radius: 5px; }"
        )
        self.summary_label.setWordWrap(True)
        main_layout.addWidget(self.summary_label)

        # Total label
        self.total_label = QLabel("Total Amount Due: ₱0.00")
        self.total_label.setAlignment(Qt.AlignCenter)
        self.total_label.setStyleSheet(
            "QLabel { color: #36454F; font-size: 32px; font-weight: bold; padding: 12px; margin: 10px 0; min-height: 60px; "
            "background-color: transparent; border-radius: 5px; }"
        )
        main_layout.addWidget(self.total_label)

        # Payment status label
        self.payment_status_label = QLabel("Click 'Enable Payment' to begin")
        self.payment_status_label.setStyleSheet(
            "font-size: 14px; color: #36454F; font-weight: bold; background-color: transparent; padding: 5px; border-radius: 3px;"
        )
        main_layout.addWidget(self.payment_status_label)

        # Amount received label
        self.amount_received_label = QLabel("Amount Received: ₱0.00")
        self.amount_received_label.setAlignment(Qt.AlignCenter)
        self.amount_received_label.setStyleSheet(
            "QLabel { color: #36454F; font-size: 24px; font-weight: bold; padding: 10px; background-color: transparent; border: none; margin: 5px 0; border-radius: 5px; }"
        )
        main_layout.addWidget(self.amount_received_label)

        # Change label
        self.change_label = QLabel("")
        self.change_label.setAlignment(Qt.AlignCenter)
        self.change_label.setStyleSheet(
            "QLabel { color: #6c757d; font-size: 18px; font-weight: bold; padding: 8px; background-color: #f8f9fa; border: none; border-radius: 6px; margin: 5px 0; }"
        )
        main_layout.addWidget(self.change_label)

        # Add simulation buttons if GPIO not available
        if not PAYMENT_GPIO_AVAILABLE:
            self._add_simulation_buttons(main_layout)

        # Add stretch to push buttons to the bottom
        main_layout.addStretch(2)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        # Back button
        self.back_btn = QPushButton("← Back to Options")
        self.back_btn.setMinimumHeight(45)
        self.back_btn.setStyleSheet(self.get_back_button_style())
        self.back_btn.clicked.connect(self.back_button_clicked.emit)

        # Enable/Disable payment button
        self.enable_payment_btn = QPushButton("Enable Payment")
        self.enable_payment_btn.setMinimumHeight(45)
        self.enable_payment_btn.setStyleSheet(self.get_enable_payment_button_style())
        self.enable_payment_btn.clicked.connect(self.payment_mode_toggle_clicked.emit)

        # Payment button
        self.payment_btn = QPushButton("Print")
        self.payment_btn.setMinimumHeight(45)
        self.payment_btn.setEnabled(False)
        self.payment_btn.setStyleSheet(self.get_payment_button_style())
        self.payment_btn.clicked.connect(self.payment_button_clicked.emit)

        button_layout.addWidget(self.back_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.enable_payment_btn)
        button_layout.addWidget(self.payment_btn)
        main_layout.addLayout(button_layout)

        stacked_layout.addWidget(self.background_label)
        stacked_layout.addWidget(foreground_widget)
        stacked_layout.setCurrentWidget(foreground_widget)
        
        # Don't set layout here - let the controller handle it
        self.main_layout = stacked_layout
    
    def _load_background_image(self):
        """Loads the background image."""
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "assets"))
        image_filename = "payment_dialog_background.png"
        abs_path = os.path.join(assets_dir, image_filename)

        if os.path.exists(abs_path):
            pixmap = QPixmap(abs_path)
            self.background_label.setPixmap(pixmap)
            self.background_label.setScaledContents(True)
        else:
            print("WARNING: Payment dialog background not found at:", abs_path)
            self.background_label.setStyleSheet("background-color: #1f1f38;")
    
    def _add_simulation_buttons(self, layout):
        """Adds simulation buttons for testing when GPIO is not available."""
        sim_label = QLabel("Simulation Mode - Test Payment:")
        sim_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #856404; background-color: #fff3cd; padding: 8px; border-radius: 4px; margin: 8px 0; }")
        layout.addWidget(sim_label)
        
        sim_layout = QHBoxLayout()
        sim_layout.setSpacing(10)
        
        for val in [1, 5, 10, 20, 50, 100]:
            btn = QPushButton(f"₱{val}")
            btn.setMinimumHeight(35)
            btn.setStyleSheet(self.get_simulation_button_style())
            if val <= 10:
                btn.clicked.connect(lambda _, v=val: self.simulation_coin_clicked.emit(v))
            else:
                btn.clicked.connect(lambda _, v=val: self.simulation_bill_clicked.emit(v))
            sim_layout.addWidget(btn)
        
        layout.addLayout(sim_layout)
    
    def update_payment_data(self, summary_data):
        """Updates the payment data display."""
        self.total_label.setText(f"Total Amount Due: ₱{summary_data['total_cost']:.2f}")
        
        summary_lines = [
            f"<b>Print Job Summary:</b>",
            f"• Document: {summary_data['document_name']}",
            f"• Copies: {summary_data['copies']}",
            f"• Color Mode: {summary_data['color_mode']}",
            f"• Breakdown: {summary_data['black_pages']} B&W pages, {summary_data['color_pages']} Color pages"
        ]
        self.summary_label.setText("<br>".join(summary_lines))
    
    def update_payment_status(self, status_text):
        """Updates the payment status label."""
        self.payment_status_label.setText(status_text)
    
    def update_amount_received(self, amount):
        """Updates the amount received display."""
        self.amount_received_label.setText(f"Amount Received: ₱{amount:.2f}")
    
    def update_change_display(self, change_amount, change_text):
        """Updates the change display."""
        self.change_label.setText(change_text)
        
        if change_amount > 0:
            # Payment complete with change
            self.change_label.setStyleSheet("QLabel { color: #155724; font-size: 18px; font-weight: bold; padding: 10px; background-color: #d4edda; border-radius: 6px; }")
        elif "Remaining" in change_text:
            # Still need more payment
            self.change_label.setStyleSheet("QLabel { color: #721c24; font-size: 18px; font-weight: bold; padding: 10px; background-color: #f8d7da; border-radius: 6px; }")
        else:
            # Payment complete, no change
            self.change_label.setStyleSheet("QLabel { color: #155724; font-size: 18px; font-weight: bold; padding: 10px; background-color: #d4edda; border-radius: 6px; }")
    
    def set_payment_button_enabled(self, enabled):
        """Enables or disables the payment button."""
        self.payment_btn.setEnabled(enabled)
    
    def set_enable_payment_button_text(self, text):
        """Sets the text for the enable/disable payment button."""
        self.enable_payment_btn.setText(text)
    
    def set_enable_payment_button_style(self, is_enabled):
        """Sets the style for the enable/disable payment button."""
        if is_enabled:
            self.enable_payment_btn.setStyleSheet(self.get_disable_payment_button_style())
        else:
            self.enable_payment_btn.setStyleSheet(self.get_enable_payment_button_style())
    
    def set_buttons_enabled(self, back_enabled, enable_payment_enabled, payment_enabled):
        """Sets the enabled state of all buttons."""
        self.back_btn.setEnabled(back_enabled)
        self.enable_payment_btn.setEnabled(enable_payment_enabled)
        self.payment_btn.setEnabled(payment_enabled)
    
    def set_payment_mode_button_state(self, is_enabled):
        """Sets the payment mode button state and text."""
        if is_enabled:
            self.enable_payment_btn.setText("Disable Payment")
            self.enable_payment_btn.setStyleSheet(self.get_disable_payment_button_style())
        else:
            self.enable_payment_btn.setText("Enable Payment")
            self.enable_payment_btn.setStyleSheet(self.get_enable_payment_button_style())
    
    def get_back_button_style(self):
        """Returns the style for the back button."""
        return (
            "QPushButton { background-color: #1e440a; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } "
            "QPushButton:hover { background-color: #2a5f10; }"
        )
    
    def get_enable_payment_button_style(self):
        """Returns the style for the enable payment button."""
        return (
            "QPushButton { background-color: #1e440a; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } "
            "QPushButton:hover { background-color: #2a5f10; }"
        )
    
    def get_disable_payment_button_style(self):
        """Returns the style for the disable payment button."""
        return (
            "QPushButton { background-color: #ffc107; color: black; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } "
            "QPushButton:hover { background-color: #e0a800; }"
        )
    
    def get_payment_button_style(self):
        """Returns the style for the payment button."""
        return (
            "QPushButton { background-color: #1e440a; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } "
            "QPushButton:hover { background-color: #2a5f10; } "
            "QPushButton:disabled { background-color: #6c757d; color: #dee2e6; }"
        )
    
    def get_simulation_button_style(self):
        """Returns the style for simulation buttons."""
        return (
            "QPushButton { background-color: #ffc107; color: black; border: none; border-radius: 4px; font-size: 12px; font-weight: bold; padding: 8px 12px; } "
            "QPushButton:hover { background-color: #e0a800; }"
        )
