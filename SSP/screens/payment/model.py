import os
import time
from PyQt5.QtCore import QObject, QThread, pyqtSignal
from managers.hopper_manager import ChangeDispenser, DispenseThread, PIGPIO_AVAILABLE as HOPPER_GPIO_AVAILABLE
from database.db_manager import DatabaseManager

try:
    import pigpio
    PAYMENT_GPIO_AVAILABLE = True
except ImportError:
    PAYMENT_GPIO_AVAILABLE = False
    print("Warning: pigpio module not available. GPIO payment acceptance will be disabled.")


class GPIOPaymentThread(QThread):
    """Thread for handling GPIO payment input (coins and bills)."""
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
        self.DEBOUNCE_TIME = 0.2  # Increased debounce time to filter noise

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
            print(f"Coin pulse detected: count={self.coin_pulse_count}, time={current_time}")  # Debug logging

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
                if self.coin_pulse_count > 0 and (now - self.coin_last_pulse_time > self.PULSE_TIMEOUT):
                    coin_value = self.get_coin_value(self.coin_pulse_count)
                    if coin_value > 0:
                        print(f"Coin value calculated: {coin_value} pesos from {self.coin_pulse_count} pulses")  # Debug logging
                        self.coin_inserted.emit(coin_value)
                    else:
                        print(f"Ignoring invalid coin pulse count: {self.coin_pulse_count} pulses")  # Debug logging
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


class PaymentModel(QObject):
    """Model for the Payment screen - handles payment logic, GPIO, and change dispensing."""
    
    # Signals for UI updates
    payment_data_updated = pyqtSignal(dict)  # payment_data
    payment_status_updated = pyqtSignal(str)  # status_message
    amount_received_updated = pyqtSignal(float)  # amount_received
    change_updated = pyqtSignal(float, str)  # change_amount, change_text
    payment_completed = pyqtSignal(dict)  # payment_info
    go_back_requested = pyqtSignal()  # request to go back
    payment_button_enabled = pyqtSignal(bool)  # enable/disable payment button
    payment_mode_changed = pyqtSignal(bool)  # payment mode enabled/disabled
    
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.total_cost = 0
        self.amount_received = 0
        self.payment_data = None
        self.cash_received = {}
        self.payment_processing = False
        self.payment_ready = False
        self.gpio_thread = None
        self.dispense_thread = None
        self.change_dispenser = ChangeDispenser()
        
    def set_payment_data(self, payment_data):
        """Sets the payment data and initializes payment state."""
        self.payment_data = payment_data
        self.total_cost = payment_data['total_cost']
        self.amount_received = 0
        self.cash_received = {}
        self.payment_ready = False
        
        # Prepare summary data for UI
        analysis = payment_data.get('analysis', {})
        pricing_info = analysis.get('pricing', {})
        b_count = pricing_info.get('black_pages_count', 0)
        c_count = pricing_info.get('color_pages_count', 0)
        doc_name = os.path.basename(payment_data['pdf_data']['path'])
        
        summary_data = {
            'total_cost': self.total_cost,
            'document_name': doc_name,
            'copies': payment_data['copies'],
            'color_mode': payment_data['color_mode'],
            'black_pages': b_count,
            'color_pages': c_count
        }
        
        self.payment_data_updated.emit(summary_data)
        self.payment_status_updated.emit("Click 'Enable Payment' to begin")
    
    def setup_gpio(self):
        """Sets up the GPIO payment thread."""
        self.gpio_thread = GPIOPaymentThread()
        self.gpio_thread.coin_inserted.connect(self.on_coin_inserted)
        self.gpio_thread.bill_inserted.connect(self.on_bill_inserted)
        self.gpio_thread.payment_status.connect(self.payment_status_updated.emit)
        self.gpio_thread.enable_acceptor.connect(self.gpio_thread.set_acceptor_state)
        self.gpio_thread.start()
    
    def enable_payment_mode(self):
        """Enables payment mode."""
        if self.total_cost <= 0:
            return
        
        self.payment_ready = True
        if self.gpio_thread:
            self.gpio_thread.enable_acceptor.emit(True)
        
        status_text = "Payment mode enabled - Use simulation buttons" if not PAYMENT_GPIO_AVAILABLE else "Payment mode enabled - Insert coins or bills"
        self.payment_status_updated.emit(status_text)
        self.payment_mode_changed.emit(True)
    
    def disable_payment_mode(self):
        """Disables payment mode."""
        self.payment_ready = False
        if self.gpio_thread:
            self.gpio_thread.enable_acceptor.emit(False)
        
        status_text = "Payment mode disabled" + (" (Simulation)" if not PAYMENT_GPIO_AVAILABLE else "")
        self.payment_status_updated.emit(status_text)
        self.payment_mode_changed.emit(False)
    
    def on_coin_inserted(self, coin_value):
        """Handles coin insertion."""
        if not self.payment_ready:
            return
        
        self.amount_received += coin_value
        self.cash_received[coin_value] = self.cash_received.get(coin_value, 0) + 1
        self.amount_received_updated.emit(self.amount_received)
        self._update_payment_status()
        self.payment_status_updated.emit(f"₱{coin_value} coin received")
    
    def on_bill_inserted(self, bill_value):
        """Handles bill insertion."""
        if not self.payment_ready:
            return
        
        self.amount_received += bill_value
        self.cash_received[bill_value] = self.cash_received.get(bill_value, 0) + 1
        self.amount_received_updated.emit(self.amount_received)
        self._update_payment_status()
        self.payment_status_updated.emit(f"₱{bill_value} bill received")
    
    def simulate_coin(self, value):
        """Simulates coin insertion for testing."""
        if self.payment_ready:
            self.on_coin_inserted(value)
    
    def simulate_bill(self, value):
        """Simulates bill insertion for testing."""
        if self.payment_ready:
            self.on_bill_inserted(value)
    
    def _update_payment_status(self):
        """Updates payment status and calculates change."""
        if self.amount_received >= self.total_cost and self.total_cost > 0:
            change = self.amount_received - self.total_cost
            change_text = f"Payment Complete. Change: ₱{change:.2f}" if change > 0 else "Payment Complete"
            self.change_updated.emit(change, change_text)
            self.payment_button_enabled.emit(True)  # Enable payment button when sufficient payment
            
            if self.payment_ready:
                self.payment_status_updated.emit("Payment sufficient - Ready to print")
                self.disable_payment_mode()
        else:
            remaining = self.total_cost - self.amount_received
            change_text = f"Remaining: ₱{remaining:.2f}"
            self.change_updated.emit(0, change_text)
            self.payment_button_enabled.emit(False)  # Disable payment button when insufficient payment
    
    def complete_payment(self, main_app):
        """Completes the payment process."""
        if self.amount_received < self.total_cost:
            return False, "Payment is not sufficient."
        
        # Check paper availability
        total_pages = len(self.payment_data['selected_pages']) * self.payment_data['copies']
        admin_screen = main_app.admin_screen
        if not admin_screen.update_paper_count(total_pages):
            return False, f"Not enough paper to complete print job.\nRequired: {total_pages} sheets. Please contact administrator to refill paper."
        
        # Process transaction
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
        
        # Update cash inventory
        for denomination, count in self.cash_received.items():
            self.db_manager.update_cash_inventory(
                denomination=denomination, 
                count=count, 
                type='bill' if denomination >= 20 else 'coin'
            )
        
        # Prepare payment info
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
        
        # Handle change dispensing
        if change_amount > 0:
            self.payment_status_updated.emit(f"Printing... Now dispensing change: ₱{change_amount:.2f}")
            self.dispense_thread = DispenseThread(self.change_dispenser, change_amount)
            self.dispense_thread.status_update.connect(self.payment_status_updated.emit)
            self.dispense_thread.dispensing_finished.connect(self._on_dispensing_finished)
            self.dispense_thread.start()
        else:
            self._on_dispensing_finished(True)
        
        return True, "Payment completed successfully"
    
    def _on_dispensing_finished(self, success):
        """Handles the completion of change dispensing."""
        if success:
            print("Dispensing complete.")
        else:
            print("CRITICAL: Error dispensing change.")
        # Signal to go to thank you screen
        self.payment_completed.emit({'navigate_to': 'thank_you'})
    
    def on_enter(self):
        """Called when the payment screen is shown."""
        print("Payment screen entered")
        self.setup_gpio()
        
        # Reset payment state
        self.payment_ready = False
        self.amount_received = 0
        self.cash_received = {}
        self.payment_processing = False
        
        self.amount_received_updated.emit(0)
        self.change_updated.emit(0, "")
        self.payment_status_updated.emit("Click 'Enable Payment' to begin")
    
    def on_leave(self):
        """Called when leaving the payment screen."""
        print("Payment screen leaving")
        
        # Stop GPIO thread safely
        if self.gpio_thread and self.gpio_thread.isRunning():
            print("Stopping GPIO thread...")
            self.gpio_thread.stop()
            if not self.gpio_thread.wait(2000):
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
    
    def go_back(self):
        """Goes back to print options screen."""
        print("Payment screen: going back to print options")
        self.on_leave()
        self.payment_data = None
        self.go_back_requested.emit()
