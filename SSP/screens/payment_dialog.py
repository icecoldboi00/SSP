# payment_dialog.py
import os
import time
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QMessageBox, QScrollArea, QStackedLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap

from screens.hopper_manager import ChangeDispenser, DispenseThread, PIGPIO_AVAILABLE as HOPPER_GPIO_AVAILABLE
from database.db_manager import DatabaseManager

try:
    import pigpio
    PAYMENT_GPIO_AVAILABLE = True
except ImportError:
    PAYMENT_GPIO_AVAILABLE = False
    print("Warning: pigpio module not available. GPIO payment acceptance will be disabled.")


class GPIOPaymentThread(QThread):
    coin_inserted = pyqtSignal(int)
    bill_inserted = pyqtSignal(int)
    payment_status = pyqtSignal(str)
    enable_acceptor = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.running = True
        self.pi = None
        self.gpio_available = PAYMENT_GPIO_AVAILABLE
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
            self.COIN_PIN, self.BILL_PIN, self.INHIBIT_PIN = 17, 18, 23
            self.pi.set_mode(self.COIN_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.COIN_PIN, pigpio.PUD_UP)
            self.pi.callback(self.COIN_PIN, pigpio.FALLING_EDGE, self.coin_pulse_detected)
            self.pi.set_mode(self.BILL_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.BILL_PIN, pigpio.PUD_UP)
            self.pi.callback(self.BILL_PIN, pigpio.FALLING_EDGE, self.bill_pulse_detected)
            self.pi.set_mode(self.INHIBIT_PIN, pigpio.OUTPUT)
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
            self.payment_status.emit(f"Bill acceptor {'enabled' if enable else 'disabled'} (simulation mode)")

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
        """Stop the GPIO thread safely."""
        print("Stopping GPIO payment thread...")
        self.running = False
        if self.gpio_available and self.pi:
            try:
                self.set_acceptor_state(False)
                self.pi.stop()
            except Exception as e:
                print(f"Error stopping GPIO: {e}")
            finally:
                self.pi = None


class PaymentScreen(QWidget):
    payment_completed = pyqtSignal(dict)
    go_back_to_viewer = pyqtSignal(dict)

    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.db_manager = DatabaseManager()
        self.total_cost, self.amount_received = 0, 0
        self.payment_data, self.cash_received = None, {}
        self.payment_processing, self.payment_ready = False, False
        self.gpio_thread, self.dispense_thread = None, None
        self.change_dispenser = ChangeDispenser()
        self.init_ui()
        # self.setup_gpio() # <-- REMOVED from __init__

    def set_payment_data(self, payment_data):
        self.payment_data = payment_data
        self.total_cost = payment_data['total_cost']
        self.amount_received, self.cash_received = 0, {}
        self.disable_payment_mode()
        self.total_label.setText(f"Total Amount Due: ₱{self.total_cost:.2f}")

        analysis = payment_data.get('analysis', {})
        pricing_info = analysis.get('pricing', {})
        b_count = pricing_info.get('black_pages_count', 0)
        c_count = pricing_info.get('color_pages_count', 0)
        doc_name = os.path.basename(payment_data['pdf_data']['path'])
        summary_lines = [
            f"<b>Print Job Summary:</b>",
            f"• Document: {doc_name}",
            f"• Copies: {payment_data['copies']}",
            f"• Color Mode: {payment_data['color_mode']}",
            f"• Breakdown: {b_count} B&W pages, {c_count} Color pages"
        ]
        self.summary_label.setText("<br>".join(summary_lines))
        self.update_payment_status()
        self.back_btn.setEnabled(True)
        self.enable_payment_btn.setEnabled(True)
        self.payment_btn.setEnabled(False)

    def init_ui(self):
        stacked_layout = QStackedLayout()
        stacked_layout.setContentsMargins(0, 0, 0, 0)
        stacked_layout.setStackingMode(QStackedLayout.StackAll)
        self.setLayout(stacked_layout)

        background_label = QLabel()
        assets_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets"))
        image_filename = "payment_dialog_background.png"
        abs_path = os.path.join(assets_dir, image_filename)

        if os.path.exists(abs_path):
            pixmap = QPixmap(abs_path)
            background_label.setPixmap(pixmap)
            background_label.setScaledContents(True)
        else:
            print("WARNING: Payment dialog background not found at:", abs_path)
            background_label.setStyleSheet("background-color: #1f1f38;")

        foreground_widget = QWidget()
        foreground_widget.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(foreground_widget)
        # --- MODIFICATION: Removed scroll area, content will be managed by main_layout ---
        main_layout.setContentsMargins(30, 20, 30, 30)
        main_layout.setSpacing(10)

        # --- MODIFICATION: Added stretch to push content down ---
        main_layout.addStretch(1)

        self.summary_label = QLabel("Print Job Summary")
        self.summary_label.setStyleSheet(
            "QLabel { color: #36454F; font-size: 16px; font-weight: normal; margin-bottom: 15px; line-height: 1.5; "
            "background-color: transparent; padding: 10px; border-radius: 5px; }"
        )
        self.summary_label.setWordWrap(True)
        main_layout.addWidget(self.summary_label)

        self.total_label = QLabel("Total Amount Due: ₱0.00")
        self.total_label.setAlignment(Qt.AlignCenter)
        self.total_label.setStyleSheet(
            "QLabel { color: #36454F; font-size: 32px; font-weight: bold; padding: 12px; margin: 10px 0; min-height: 60px; "
            "background-color: transparent; border-radius: 5px; }"
        )
        main_layout.addWidget(self.total_label)

        self.payment_status_label = QLabel("Click 'Enable Payment' to begin")
        self.payment_status_label.setStyleSheet(
            "font-size: 14px; color: #36454F; font-weight: bold; background-color: transparent; padding: 5px; border-radius: 3px;"
        )
        main_layout.addWidget(self.payment_status_label)

        self.amount_received_label = QLabel("Amount Received: ₱0.00")
        self.amount_received_label.setAlignment(Qt.AlignCenter)
        self.amount_received_label.setStyleSheet(
            "QLabel { color: #36454F; font-size: 24px; font-weight: bold; padding: 10px; background-color: transparent; border: none; margin: 5px 0; border-radius: 5px; }"
        )
        main_layout.addWidget(self.amount_received_label)

        self.change_label = QLabel("")
        self.change_label.setAlignment(Qt.AlignCenter)
        self.change_label.setStyleSheet(
            "QLabel { color: #6c757d; font-size: 18px; font-weight: bold; padding: 8px; background-color: #f8f9fa; border: none; border-radius: 6px; margin: 5px 0; }"
        )
        main_layout.addWidget(self.change_label)

        if not PAYMENT_GPIO_AVAILABLE:
            self.add_simulation_buttons(main_layout)

        # --- MODIFICATION: Add stretch to push buttons to the bottom ---
        main_layout.addStretch(2)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        self.back_btn = QPushButton("← Back to Options")
        self.back_btn.setMinimumHeight(45)
        self.back_btn.setStyleSheet(
            "QPushButton { background-color: #1e440a; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } "
            "QPushButton:hover { background-color: #2a5f10; }"
        )
        self.back_btn.clicked.connect(self.go_back)

        self.enable_payment_btn = QPushButton("Enable Payment")
        self.enable_payment_btn.setMinimumHeight(45)
        self.enable_payment_btn.setStyleSheet(
            "QPushButton { background-color: #1e440a; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } "
            "QPushButton:hover { background-color: #2a5f10; }"
        )
        self.enable_payment_btn.clicked.connect(self.enable_payment_mode)

        self.payment_btn = QPushButton("Print")
        self.payment_btn.setMinimumHeight(45)
        self.payment_btn.setEnabled(False)
        self.payment_btn.setStyleSheet(
            "QPushButton { background-color: #1e440a; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } "
            "QPushButton:hover { background-color: #2a5f10; } QPushButton:disabled { background-color: #6c757d; color: #dee2e6; }"
        )
        self.payment_btn.clicked.connect(self.complete_payment)

        button_layout.addWidget(self.back_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.enable_payment_btn)
        button_layout.addWidget(self.payment_btn)
        main_layout.addLayout(button_layout)

        stacked_layout.addWidget(background_label)
        stacked_layout.addWidget(foreground_widget)
        stacked_layout.setCurrentWidget(foreground_widget)

    def setup_gpio(self):
        self.gpio_thread = GPIOPaymentThread()
        self.gpio_thread.coin_inserted.connect(self.on_coin_inserted)
        self.gpio_thread.bill_inserted.connect(self.on_bill_inserted)
        self.gpio_thread.payment_status.connect(self.on_payment_status)
        self.gpio_thread.enable_acceptor.connect(self.gpio_thread.set_acceptor_state)
        self.gpio_thread.start()

    def add_simulation_buttons(self, layout):
        sim_label = QLabel("Simulation Mode - Test Payment:")
        sim_label.setStyleSheet("QLabel { font-size: 14px; font-weight: bold; color: #856404; background-color: #fff3cd; padding: 8px; border-radius: 4px; margin: 8px 0; }")
        layout.addWidget(sim_label)
        sim_layout = QHBoxLayout()
        sim_layout.setSpacing(10)
        for val in [1, 5, 10, 20, 50, 100]:
            btn = QPushButton(f"₱{val}")
            btn.setMinimumHeight(35)
            btn.setStyleSheet("QPushButton { background-color: #ffc107; color: black; border: none; border-radius: 4px; font-size: 12px; font-weight: bold; padding: 8px 12px; } QPushButton:hover { background-color: #e0a800; }")
            btn.clicked.connect(lambda _, v=val: (self.simulate_coin(v) if v <= 10 else self.simulate_bill(v)))
            sim_layout.addWidget(btn)
        layout.addLayout(sim_layout)

    def simulate_coin(self, value):
        if self.payment_ready:
            self.on_coin_inserted(value)

    def simulate_bill(self, value):
        if self.payment_ready:
            self.on_bill_inserted(value)

    def enable_payment_mode(self):
        if self.total_cost <= 0:
            return
        self.payment_ready = True
        if self.gpio_thread:
            self.gpio_thread.enable_acceptor.emit(True)

        self.enable_payment_btn.setText("Disable Payment")
        self.enable_payment_btn.setStyleSheet("QPushButton { background-color: #ffc107; color: black; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } QPushButton:hover { background-color: #e0a800; }")
        try:
            self.enable_payment_btn.clicked.disconnect()
        except Exception:
            pass
        self.enable_payment_btn.clicked.connect(self.disable_payment_mode)

        status_text = "Payment mode enabled - Use simulation buttons" if not PAYMENT_GPIO_AVAILABLE else "Payment mode enabled - Insert coins or bills"
        self.payment_status_label.setText(status_text)
        self.payment_status_label.setStyleSheet("color: #36454F; font-size: 14px; font-weight: bold; background-color: transparent; padding: 5px; border-radius: 3px;")

    def disable_payment_mode(self):
        self.payment_ready = False
        if self.gpio_thread:
            self.gpio_thread.enable_acceptor.emit(False)

        self.enable_payment_btn.setText("Enable Payment")
        self.enable_payment_btn.setStyleSheet("QPushButton { background-color: #1e440a; color: white; border: none; border-radius: 6px; font-size: 16px; font-weight: bold; padding: 12px 24px; } QPushButton:hover { background-color: #2a5f10; }")
        try:
            self.enable_payment_btn.clicked.disconnect()
        except Exception:
            pass
        self.enable_payment_btn.clicked.connect(self.enable_payment_mode)

        status_text = "Payment mode disabled" + (" (Simulation)" if not PAYMENT_GPIO_AVAILABLE else "")
        self.payment_status_label.setText(status_text)
        self.payment_status_label.setStyleSheet("color: #36454F; font-size: 14px; font-weight: bold; background-color: transparent; padding: 5px; border-radius: 3px;")

    def on_coin_inserted(self, coin_value):
        if not self.payment_ready:
            return
        self.amount_received += coin_value
        self.cash_received[coin_value] = self.cash_received.get(coin_value, 0) + 1
        self.update_payment_status()
        self.payment_status_label.setText(f"₱{coin_value} coin received")

    def on_bill_inserted(self, bill_value):
        if not self.payment_ready:
            return
        self.amount_received += bill_value
        self.cash_received[bill_value] = self.cash_received.get(bill_value, 0) + 1
        self.update_payment_status()
        self.payment_status_label.setText(f"₱{bill_value} bill received")

    def on_payment_status(self, status):
        self.payment_status_label.setText(status)

    def update_payment_status(self):
        self.amount_received_label.setText(f"Amount Received: ₱{self.amount_received:.2f}")
        if self.amount_received >= self.total_cost and self.total_cost > 0:
            change = self.amount_received - self.total_cost
            self.change_label.setText(f"Payment Complete. Change: ₱{change:.2f}" if change > 0 else "Payment Complete")
            self.change_label.setStyleSheet("QLabel { color: #155724; font-size: 18px; font-weight: bold; padding: 10px; background-color: #d4edda; border-radius: 6px; }")
            self.payment_btn.setEnabled(True)
            if self.payment_ready:
                self.payment_status_label.setText("Payment sufficient - Ready to print")
                self.disable_payment_mode()
        else:
            remaining = self.total_cost - self.amount_received
            self.change_label.setText(f"Remaining: ₱{remaining:.2f}")
            self.change_label.setStyleSheet("QLabel { color: #721c24; font-size: 18px; font-weight: bold; padding: 10px; background-color: #f8d7da; border-radius: 6px; }")
            self.payment_btn.setEnabled(False)

    def complete_payment(self):
        if self.amount_received < self.total_cost:
            QMessageBox.warning(self, "Insufficient Payment", "Payment is not sufficient.")
            return

        total_pages = len(self.payment_data['selected_pages']) * self.payment_data['copies']
        admin_screen = self.main_app.admin_screen
        if not admin_screen.update_paper_count(total_pages):
            QMessageBox.critical(self, "Out of Paper", f"Not enough paper to complete print job.\n"
                                f"Required: {total_pages} sheets. Please contact administrator to refill paper.")
            return

        change_amount = self.amount_received - self.total_cost
        transaction_data = {
            'file_name': os.path.basename(self.payment_data['pdf_data']['path']),
            'pages': len(self.payment_data['selected_pages']),
            'copies': self.payment_data['copies'],
            'color_mode': self.payment_data['color_mode'],
            'total_cost': self.total_cost,
            'amount_paid': self.amount_received,
            'change_given': change_amount,
            'status': 'completed'
        }
        self.db_manager.log_transaction(transaction_data)

        for denomination, count in self.cash_received.items():
            self.db_manager.update_cash_inventory(denomination=denomination, count=count, type='bill' if denomination >= 20 else 'coin')

        payment_info = {
            'pdf_data': self.payment_data['pdf_data'],
            'selected_pages': self.payment_data['selected_pages'],
            'color_mode': self.payment_data['color_mode'],
            'copies': self.payment_data['copies'],
            'total_cost': self.total_cost,
            'amount_received': self.amount_received,
            'change': change_amount,
            'payment_method': 'Cash' if PAYMENT_GPIO_AVAILABLE else 'Simulation'
        }
        self.payment_completed.emit(payment_info)

        self.back_btn.setEnabled(False)
        self.enable_payment_btn.setEnabled(False)
        self.payment_btn.setEnabled(False)

        if change_amount > 0:
            self.payment_status_label.setText(f"Printing... Now dispensing change: ₱{change_amount:.2f}")
            self.payment_status_label.setStyleSheet("color: #007bff; font-weight: bold; font-size: 14px;")
            self.dispense_thread = DispenseThread(self.change_dispenser, change_amount)
            self.dispense_thread.status_update.connect(self.on_dispense_status_update)
            self.dispense_thread.dispensing_finished.connect(self.on_dispensing_finished)
            self.dispense_thread.start()
        else:
            self.main_app.show_screen('thank_you')

    def on_dispense_status_update(self, message: str):
        self.payment_status_label.setText(f"Dispensing... {message}")

    def on_dispensing_finished(self, success: bool):
        if success:
            print("Dispensing complete.")
        else:
            print("CRITICAL: Error dispensing change.")
        self.main_app.show_screen('thank_you')

    def go_back(self):
        """Go back to print options screen."""
        print("Payment screen: going back to print options")
        # Use the on_leave method to properly clean up
        self.on_leave()
        
        # Reset payment data
        self.payment_data = None
        
        if hasattr(self.main_app, 'show_screen'):
            self.main_app.show_screen('printing_options')

    def on_enter(self):
        """Called when the payment screen is shown."""
        print("Payment screen entered")
        
        # Start a fresh GPIO thread every time the screen is entered to ensure
        # the connection to the pigpio daemon is active.
        self.setup_gpio()
        
        # Reset payment state when entering the screen
        self.payment_ready = False
        self.amount_received = 0
        self.cash_received = {}
        self.payment_processing = False
        
        # Update UI to reflect reset state
        self.amount_received_label.setText("Amount Received: ₱0.00")
        self.change_label.setText("")
        self.payment_status_label.setText("Click 'Enable Payment' to begin")
        
        # Re-enable buttons
        self.back_btn.setEnabled(True)
        self.enable_payment_btn.setEnabled(True)
        self.payment_btn.setEnabled(False)

    def on_leave(self):
        """Called when leaving the payment screen."""
        print("Payment screen leaving")
        # Stop GPIO thread safely
        if self.gpio_thread and self.gpio_thread.isRunning():
            print("Stopping GPIO thread...")
            self.gpio_thread.stop()
            if not self.gpio_thread.wait(2000):  # Wait up to 2 seconds
                print("Warning: GPIO thread did not stop gracefully")
                self.gpio_thread.terminate()
                self.gpio_thread.wait(1000)
        
        # Clean up change dispenser
        try:
            if hasattr(self, 'change_dispenser'):
                self.change_dispenser.cleanup()
        except Exception as e:
            print(f"Error cleaning up change dispenser: {e}")
        
        # Stop any running dispense thread
        if hasattr(self, 'dispense_thread') and self.dispense_thread and self.dispense_thread.isRunning():
            print("Stopping dispense thread...")
            self.dispense_thread.terminate()
            self.dispense_thread.wait(1000)