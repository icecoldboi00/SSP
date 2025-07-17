from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QScrollArea, QFrame, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
import time

# Try to import pigpio, but continue without it if not available
try:
    import pigpio
    PIGPIO_AVAILABLE = True
except ImportError:
    PIGPIO_AVAILABLE = False
    print("Warning: pigpio module not available. GPIO payment functionality will be disabled.")

class GPIOPaymentThread(QThread):
    coin_inserted = pyqtSignal(int)
    bill_inserted = pyqtSignal(int)
    payment_status = pyqtSignal(str)
    enable_acceptor = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.running = True
        self.pi = None
        self.gpio_available = PIGPIO_AVAILABLE

        if self.gpio_available:
            self.setup_gpio()
        else:
            self.setup_mock_gpio()

        self.coin_pulse_count = 0
        self.coin_last_pulse_time = time.time()
        self.bill_pulse_count = 0
        self.bill_last_pulse_time = time.time()

        self.COIN_TIMEOUT = 0.5
        self.PULSE_TIMEOUT = 0.5
        self.DEBOUNCE_TIME = 0.1

    def setup_gpio(self):
        try:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                raise Exception("Could not connect to pigpio daemon")
            self.COIN_PIN = 17
            self.BILL_PIN = 18
            self.INHIBIT_PIN = 23
            self.pi.set_mode(self.COIN_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.COIN_PIN, pigpio.PUD_UP)
            self.pi.callback(self.COIN_PIN, pigpio.FALLING_EDGE, self.coin_pulse_detected)
            self.pi.set_mode(self.BILL_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.BILL_PIN, pigpio.PUD_UP)
            self.pi.set_mode(self.INHIBIT_PIN, pigpio.OUTPUT)
            self.pi.callback(self.BILL_PIN, pigpio.FALLING_EDGE, self.bill_pulse_detected)
            self.set_acceptor_state(False)
            self.payment_status.emit("Payment system ready - Bill acceptor disabled")
        except Exception as e:
            self.payment_status.emit(f"GPIO Error: {str(e)}")
            self.gpio_available = False

    def setup_mock_gpio(self):
        self.payment_status.emit("GPIO not available - Payment system running in simulation mode")

    def set_acceptor_state(self, enable):
        if self.gpio_available and self.pi:
            self.pi.write(self.INHIBIT_PIN, 0 if enable else 1)
        else:
            status = "enabled" if enable else "disabled"
            self.payment_status.emit(f"Bill acceptor {status} (simulation mode)")

    def coin_pulse_detected(self, gpio, level, tick):
        current_time = time.time()
        if current_time - self.coin_last_pulse_time > self.DEBOUNCE_TIME:
            self.coin_pulse_count += 1
            self.coin_last_pulse_time = current_time

    def bill_pulse_detected(self, gpio, level, tick):
        current_time = time.time()
        if current_time - self.bill_last_pulse_time > self.DEBOUNCE_TIME:
            self.bill_pulse_count += 1
            self.bill_last_pulse_time = current_time

    def get_coin_value(self, pulses):
        if pulses == 1:
            return 1
        elif 5 <= pulses <= 7:
            return 5
        elif 10 <= pulses <= 12:
            return 10
        else:
            return 0

    def get_bill_value(self, pulses):
        if pulses == 2:
            return 20
        elif pulses == 5:
            return 50
        elif pulses == 10:
            return 100
        elif pulses == 50:
            return 500
        else:
            return 0

    def run(self):
        while self.running:
            now = time.time()
            if self.gpio_available:
                if self.coin_pulse_count > 0 and (now - self.coin_last_pulse_time > self.COIN_TIMEOUT):
                    coin_value = self.get_coin_value(self.coin_pulse_count)
                    if coin_value > 0:
                        self.coin_inserted.emit(coin_value)
                    self.coin_pulse_count = 0
                if self.bill_pulse_count > 0 and (now - self.bill_last_pulse_time > self.PULSE_TIMEOUT):
                    bill_value = self.get_bill_value(self.bill_pulse_count)
                    if bill_value > 0:
                        self.bill_inserted.emit(bill_value)
                    self.bill_pulse_count = 0
            time.sleep(0.05)

    def stop(self):
        self.running = False
        if self.gpio_available and self.pi:
            self.set_acceptor_state(False)
            self.pi.stop()

class PaymentScreen(QWidget):
    payment_completed = pyqtSignal(dict)
    go_back_to_viewer = pyqtSignal(dict)

    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.total_cost = 0
        self.payment_data = None
        self.payment_processing = False
        self.amount_received = 0
        self.gpio_thread = None
        self.payment_ready = False

        self.init_ui()
        self.setup_gpio()
    
    def set_payment_data(self, payment_data):
        """Set payment data received from Print Options screen"""
        self.payment_data = payment_data
        self.total_cost = payment_data['total_cost']
        
        # Update UI
        self.total_label.setText(f"Total Amount Due: ₱{self.total_cost:.2f}")
        summary = (f"Print Job Summary:\n"
                  f"• Pages: {len(payment_data['selected_pages'])}\n"
                  f"• Copies: {payment_data['copies']}\n"
                  f"• Mode: {payment_data['color_mode']}\n"
                  f"• Price per page: ₱{payment_data['price_per_page']:.2f}")
        self.summary_label.setText(summary)
        self.update_payment_status()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 30, 30, 30)
        content_layout.setSpacing(20)

        # Order Summary
        self.summary_label = QLabel("Print Job Summary")
        self.summary_label.setStyleSheet("""
            QLabel {
                color: black;
                font-size: 24px;
                font-weight: bold;
                margin-bottom: 15px;
            }
        """)
        content_layout.addWidget(self.summary_label)

        # Total Amount Display
        self.total_label = QLabel("Total Amount Due: ₱0.00")
        self.total_label.setAlignment(Qt.AlignCenter)
        self.total_label.setStyleSheet("""
            QLabel {
                color: black;
                font-size: 32px;
                font-weight: bold;
                padding: 12px;
                margin: 15px 0;
                min-height: 60px;
            }
        """)
        content_layout.addWidget(self.total_label)

        # Payment Status
        self.payment_status_label = QLabel("Click 'Enable Payment' to begin")
        self.payment_status_label.setStyleSheet("font-size: 14px; color: #6c757d;")
        content_layout.addWidget(self.payment_status_label)

        # Amount Received Display
        self.amount_received_label = QLabel("Amount Received: ₱0.00")
        self.amount_received_label.setAlignment(Qt.AlignCenter)
        self.amount_received_label.setStyleSheet("""
            QLabel {
                color: #28a745;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
                background-color: white;
                border: none;
                margin: 10px 0;
            }
        """)
        content_layout.addWidget(self.amount_received_label)

        # Change/Remaining Display
        self.change_label = QLabel("")
        self.change_label.setAlignment(Qt.AlignCenter)
        self.change_label.setStyleSheet("""
            QLabel {
                color: #6c757d;
                font-size: 18px;
                font-weight: bold;
                padding: 8px;
                background-color: #f8f9fa;
                border: none;
                border-radius: 6px;
                margin: 5px 0;
            }
        """)
        content_layout.addWidget(self.change_label)

        # Add simulation buttons if no GPIO
        if not PIGPIO_AVAILABLE:
            self.add_simulation_buttons(content_layout)

        # Control Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        # Back button
        self.back_btn = QPushButton("← Back to Options")
        self.back_btn.setMinimumHeight(45)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #4d4d80;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #5d5d90;
            }
        """)
        self.back_btn.clicked.connect(self.go_back)

        # Enable Payment button
        self.enable_payment_btn = QPushButton("Enable Payment")
        self.enable_payment_btn.setMinimumHeight(45)
        self.enable_payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.enable_payment_btn.clicked.connect(self.enable_payment_mode)

        # Add payment button (after the enable_payment_btn)
        self.payment_btn = QPushButton("Complete Payment & Print")
        self.payment_btn.setMinimumHeight(45)
        self.payment_btn.setEnabled(False)  # Initially disabled until payment is sufficient
        self.payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #dee2e6;
            }
        """)
        self.payment_btn.clicked.connect(self.complete_payment)

        button_layout.addWidget(self.back_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.enable_payment_btn)
        button_layout.addWidget(self.payment_btn)  # Add payment button to layout
        content_layout.addLayout(button_layout)

        scroll.setWidget(content)

    def setup_gpio(self):
        self.gpio_thread = GPIOPaymentThread()
        self.gpio_thread.coin_inserted.connect(self.on_coin_inserted)
        self.gpio_thread.bill_inserted.connect(self.on_bill_inserted)
        self.gpio_thread.payment_status.connect(self.on_payment_status)
        self.gpio_thread.enable_acceptor.connect(self.gpio_thread.set_acceptor_state)
        self.gpio_thread.start()

    def add_simulation_buttons(self, layout):
        sim_label = QLabel("Simulation Mode - Test Payment:")
        sim_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
                color: #ffc107;
                background-color: #fff3cd;
                padding: 8px;
                border-radius: 4px;
                margin: 8px 0;
            }
        """)
        layout.addWidget(sim_label)

        sim_layout = QHBoxLayout()
        sim_layout.setSpacing(10)

        coin_1_btn = QPushButton("₱1")
        coin_5_btn = QPushButton("₱5")
        coin_10_btn = QPushButton("₱10")
        bill_20_btn = QPushButton("₱20")
        bill_50_btn = QPushButton("₱50")
        bill_100_btn = QPushButton("₱100")

        sim_buttons = [coin_1_btn, coin_5_btn, coin_10_btn, bill_20_btn, bill_50_btn, bill_100_btn]

        for btn in sim_buttons:
            btn.setMinimumHeight(35)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #ffc107;
                    color: black;
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 8px 12px;
                }
                QPushButton:hover {
                    background-color: #e0a800;
                }
            """)
            sim_layout.addWidget(btn)

        coin_1_btn.clicked.connect(lambda: self.simulate_coin(1))
        coin_5_btn.clicked.connect(lambda: self.simulate_coin(5))
        coin_10_btn.clicked.connect(lambda: self.simulate_coin(10))
        bill_20_btn.clicked.connect(lambda: self.simulate_bill(20))
        bill_50_btn.clicked.connect(lambda: self.simulate_bill(50))
        bill_100_btn.clicked.connect(lambda: self.simulate_bill(100))

        layout.addLayout(sim_layout)

    def simulate_coin(self, value):
        if self.payment_ready:
            self.on_coin_inserted(value)

    def simulate_bill(self, value):
        if self.payment_ready:
            self.on_bill_inserted(value)

    def enable_payment_mode(self):
        if self.total_cost <= 0:
            QMessageBox.warning(self, "Invalid Amount", "Please set a valid print job first")
            return
        self.payment_ready = True
        if self.gpio_thread:
            self.gpio_thread.enable_acceptor.emit(True)
        self.enable_payment_btn.setText("Disable Payment")
        self.enable_payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: black;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        self.enable_payment_btn.clicked.disconnect()
        self.enable_payment_btn.clicked.connect(self.disable_payment_mode)
        status_text = "Payment mode enabled - Insert coins or bills"
        if not PIGPIO_AVAILABLE:
            status_text = "Payment mode enabled - Use simulation buttons to test"
        self.payment_status_label.setText(status_text)
        self.payment_status_label.setStyleSheet("color: #28a745; font-size: 14px; font-weight: bold;")

    def disable_payment_mode(self):
        self.payment_ready = False
        if self.gpio_thread:
            self.gpio_thread.enable_acceptor.emit(False)
        self.enable_payment_btn.setText("Enable Payment")
        self.enable_payment_btn.setStyleSheet("""
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
        """)
        self.enable_payment_btn.clicked.disconnect()
        self.enable_payment_btn.clicked.connect(self.enable_payment_mode)
        status_text = "Payment mode disabled - Click 'Enable Payment' to start"
        if not PIGPIO_AVAILABLE:
            status_text = "Payment mode disabled - Running in simulation mode"
        self.payment_status_label.setText(status_text)
        self.payment_status_label.setStyleSheet("color: #6c757d; font-size: 14px;")

    def on_coin_inserted(self, coin_value):
        if not self.payment_ready:
            return
        self.amount_received += coin_value
        self.update_payment_status()
        self.payment_status_label.setText(f"₱{coin_value} coin received")

    def on_bill_inserted(self, bill_value):
        if not self.payment_ready:
            return
        self.amount_received += bill_value
        self.update_payment_status()
        self.payment_status_label.setText(f"₱{bill_value} bill received")

    def on_payment_status(self, status):
        self.payment_status_label.setText(status)

    def update_payment_status(self):
        """Update the payment status display based on amount received."""
        self.amount_received_label.setText(f"Amount Received: ₱{self.amount_received:.2f}")
        
        if self.amount_received >= self.total_cost and self.total_cost > 0:
            change = self.amount_received - self.total_cost
            if change > 0:
                self.change_label.setText(f"Change: ₱{change:.2f}")
                self.change_label.setStyleSheet("""
                    QLabel {
                        color: #ffc107;
                        font-size: 18px;
                        font-weight: bold;
                        padding: 10px;
                        background-color: #fff3cd;
                        border: none;
                        border-radius: 6px;
                        margin: 5px 0;
                    }
                """)
            else:
                self.change_label.setText("Payment Complete")
                self.change_label.setStyleSheet("""
                    QLabel {
                        color: #28a745;
                        font-size: 18px;
                        font-weight: bold;
                        padding: 10px;
                        background-color: #d4edda;
                        border: none;
                        border-radius: 6px;
                        margin: 5px 0;
                    }
                """)
            self.payment_btn.setEnabled(True)
            if self.payment_ready:
                self.payment_status_label.setText("Payment sufficient - Ready to print")
                self.payment_status_label.setStyleSheet("color: #28a745; font-size: 14px; font-weight: bold;")
                self.disable_payment_mode()
        else:
            remaining = self.total_cost - self.amount_received
            self.change_label.setText(f"Remaining: ₱{remaining:.2f}")
            self.change_label.setStyleSheet("""
                QLabel {
                    color: #dc3545;
                    font-size: 18px;
                    font-weight: bold;
                    padding: 10px;
                    background-color: #f8d7da;
                    border: none;
                    border-radius: 6px;
                    margin: 5px 0;
                }
            """)
            self.payment_btn.setEnabled(False)

    def complete_payment(self):
        """Handle payment completion and transition to printing"""
        if self.amount_received >= self.total_cost:
            payment_info = {
                'pdf_data': self.payment_data['pdf_data'],
                'selected_pages': self.payment_data['selected_pages'],
                'color_mode': self.payment_data['color_mode'],
                'copies': self.payment_data['copies'],
                'total_cost': self.total_cost,
                'amount_received': self.amount_received,
                'change': self.amount_received - self.total_cost,
                'payment_method': 'Cash Payment' if PIGPIO_AVAILABLE else 'Simulation'
            }
            
            # Emit payment completion signal and return to idle
            self.payment_completed.emit(payment_info)
            
            # Show success message
            QMessageBox.information(self, "Payment Complete", 
                f"Payment successful!\nChange: ₱{payment_info['change']:.2f}\n\nPrinting will begin shortly...")
            
            # Go back to idle screen
            self.main_app.show_screen('idle')
        else:
            remaining = self.total_cost - self.amount_received
            QMessageBox.warning(self, "Insufficient Payment", 
                f"Please insert ₱{remaining:.2f} more")

    def cancel_transaction(self):
        """Immediately go to idle, cancel everything."""
        if self.gpio_thread:
            self.gpio_thread.stop()
            self.gpio_thread.wait(3000)
        if hasattr(self.main_app, "show_screen"):
            self.main_app.show_screen("idle")

    def back_to_viewer(self):
        """Go back to file browser/viewer screen with current settings."""
        # Pass back all state, including all_pages_state if present
        payment_return = {
            'pdf_data': self.payment_data.copy(),
            'total_cost': self.total_cost,
            'amount_received': self.amount_received
        }
        
        self.go_back_to_viewer.emit(payment_return)
        
        # Return to printing options screen
        if hasattr(self.main_app, 'show_screen'):
            self.main_app.show_screen('printing_options')

    def go_back(self):
        """Return to printing options screen"""
        if self.gpio_thread:
            self.gpio_thread.stop()
            self.gpio_thread.wait(3000)
        
        # Reset payment state
        self.payment_ready = False
        self.amount_received = 0
        self.payment_data = None
        
        # Update UI
        self.amount_received_label.setText("Amount Received: ₱0.00")
        self.change_label.setText("")
        self.payment_status_label.setText("Click 'Enable Payment' to begin")
        
        # Return to printing options screen
        if hasattr(self.main_app, 'show_screen'):
            self.main_app.show_screen('printing_options')
