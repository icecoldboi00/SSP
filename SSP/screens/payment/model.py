import os
import time
import threading
from typing import Tuple, List, Dict
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QTimer
from managers.hopper_manager import ChangeDispenser, DispenseThread, PIGPIO_AVAILABLE as HOPPER_GPIO_AVAILABLE
from managers.payment_algorithm_manager import PaymentAlgorithmManager
from database.db_manager import DatabaseManager

# Removed persistent GPIO import - using original GPIOPaymentThread instead


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
        # Check for pigpio availability
        try:
            import pigpio
            self.gpio_available = True
        except ImportError:
            self.gpio_available = False
        if self.gpio_available:
            self.setup_gpio()
        else:
            self.setup_mock_gpio()

        self.coin_pulse_count = 0
        self.coin_last_pulse_time = time.time()
        self.bill_pulse_count = 0
        self.bill_last_pulse_time = time.time()
        self.COIN_TIMEOUT = 0.5    # seconds without pulses = end of coin
        self.PULSE_TIMEOUT = 0.5   # Time to wait for additional bill pulses
        self.DEBOUNCE_TIME = 0.1   # Minimum time between pulses

        # Coin pulse aggregation (prevents 1 coin being counted multiple times)
        self.accepting_coin = True
        self.pulse_aggregator = QTimer()
        self.pulse_aggregator.setSingleShot(True)
        self.pulse_aggregator.setInterval(150)  # ms of quiet defines coin boundary
        self.pulse_aggregator.timeout.connect(self._on_pulse_aggregation_timeout)

        self.coin_cooldown = QTimer()
        self.coin_cooldown.setSingleShot(True)
        self.coin_cooldown.setInterval(200)  # brief lockout after a coin
        self.coin_cooldown.timeout.connect(self._end_coin_cooldown)

        # Print-related attributes
        self.print_file_path = None

        # Payment tracking attributes
        self.cash_received = {}
        self.change_dispensed = {}
        self.selected_pages = None
        self.copies = 1
        self.color_mode = "Color"

    def setup_gpio(self):
        try:
            self.pi = pigpio.pi()
            if not self.pi.connected:
                raise Exception("Could not connect to pigpio daemon")
            self.COIN_PIN, self.BILL_PIN, self.INHIBIT_PIN, self.COIN_INHIBIT_PIN = 17, 18, 23, 22

            # Setup coin acceptor GPIO
            self.pi.set_mode(self.COIN_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.COIN_PIN, pigpio.PUD_UP)
            self.pi.callback(self.COIN_PIN, pigpio.FALLING_EDGE, self.coin_pulse_detected)

            # Setup coin acceptor inhibit pin (pin 22)
            self.pi.set_mode(self.COIN_INHIBIT_PIN, pigpio.OUTPUT)
            self.set_coin_acceptor_state(False)  # Start disabled (pin 22 = 0)

            # Setup bill acceptor GPIO
            self.pi.set_mode(self.BILL_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.BILL_PIN, pigpio.PUD_UP)
            self.pi.set_mode(self.INHIBIT_PIN, pigpio.OUTPUT)
            self.set_acceptor_state(False)  # Start disabled
            self.pi.callback(self.BILL_PIN, pigpio.FALLING_EDGE, self.bill_pulse_detected)

            self.payment_status.emit("Payment system ready - Coin and bill acceptors disabled")
        except Exception as e:
            self.payment_status.emit(f"GPIO Error: {str(e)}")
            self.gpio_available = False

    def setup_mock_gpio(self):
        self.payment_status.emit("GPIO not available - Payment system running in simulation mode")

    def set_acceptor_state(self, enable):
        if self.gpio_available and self.pi:
            self.pi.write(self.INHIBIT_PIN, 0 if enable else 1)  # LOW = enabled, HIGH = disabled
            print(f"Bill acceptor {'enabled' if enable else 'disabled'}")
        else:
            self.payment_status.emit(f"Bill acceptor {'enabled' if enable else 'disabled'} (simulation mode)")

    def set_coin_acceptor_state(self, enable):
        if self.gpio_available and self.pi:
            self.pi.write(self.COIN_INHIBIT_PIN, 1 if enable else 0)  # HIGH = enabled, LOW = disabled
            print(f"Coin acceptor {'enabled' if enable else 'disabled'}")
        else:
            self.payment_status.emit(f"Coin acceptor {'enabled' if enable else 'disabled'} (simulation mode)")

    def coin_pulse_detected(self, gpio, level, tick):
        # Debounce and aggregate pulses into a single coin event
        if not self.accepting_coin:
            return
        current_time = time.time()
        if current_time - self.coin_last_pulse_time > self.DEBOUNCE_TIME:
            self.coin_pulse_count += 1
            self.coin_last_pulse_time = current_time
            # Restart aggregation window
            if self.pulse_aggregator.isActive():
                self.pulse_aggregator.stop()
            self.pulse_aggregator.start()

    def _on_pulse_aggregation_timeout(self):
        # Called when no pulses arrived within the aggregation window
        pulses = self.coin_pulse_count
        self.coin_pulse_count = 0
        value = self.get_coin_value(pulses)
        if value > 0:
            self.coin_inserted.emit(value)
        # Start cooldown to avoid immediate retrigger
        self.accepting_coin = False
        self.coin_cooldown.start()

    def _end_coin_cooldown(self):
        self.accepting_coin = True

    def bill_pulse_detected(self, gpio, level, tick):
        current_time = time.time()
        if current_time - self.bill_last_pulse_time > self.DEBOUNCE_TIME:
            self.bill_pulse_count += 1
            self.bill_last_pulse_time = current_time

    def get_coin_value(self, pulses):
        # Fixed coin detection logic - each coin type has specific pulse count
        print(f"DEBUG: Processing {pulses} coin pulses")

        if pulses == 1:
            print("DEBUG: Detected ₱1 coin (1 pulse)")
            return 1  # ₱1 coin = 1 pulse
        elif pulses == 5:
            print("DEBUG: Detected ₱5 coin (5 pulses)")
            return 5  # ₱5 coin = 5 pulses
        elif pulses == 10:
            print("DEBUG: Detected ₱10 coin (10 pulses)")
            return 10  # ₱10 coin = 10 pulses
        elif pulses == 20:
            print("DEBUG: Detected ₱20 coin (20 pulses)")
            return 20  # ₱20 coin = 20 pulses
        # Handle ranges for coins that might have slight variations
        elif 4 <= pulses <= 6:
            print(f"DEBUG: Detected ₱5 coin with variation ({pulses} pulses)")
            return 5  # ₱5 coin with slight variation
        elif 9 <= pulses <= 11:
            print(f"DEBUG: Detected ₱10 coin with variation ({pulses} pulses)")
            return 10  # ₱10 coin with slight variation
        elif 18 <= pulses <= 22:
            print(f"DEBUG: Detected ₱20 coin with variation ({pulses} pulses)")
            return 20  # ₱20 coin with slight variation
        else:
            print(f"DEBUG: Unknown coin pulse count: {pulses} - returning 0")
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
                # Coin events are handled by QTimer aggregation now
                if self.bill_pulse_count > 0 and (now - self.bill_last_pulse_time > self.PULSE_TIMEOUT):
                    bill_value = self.get_bill_value(self.bill_pulse_count)
                    if bill_value > 0:
                        self.bill_inserted.emit(bill_value)
                    self.bill_pulse_count = 0
            time.sleep(0.05)

    def enable_payment(self):
        """Enable payment acceptors."""
        print("DEBUG: GPIOPaymentThread.enable_payment() called")
        if self.gpio_available:
            self.set_acceptor_state(True)  # Enable bill acceptor
            self.set_coin_acceptor_state(True)  # Enable coin acceptor
            print("SUCCESS: Payment acceptors enabled")
        else:
            print("WARNING: GPIO not available - payment acceptors not enabled")

    def disable_payment(self):
        """Disable payment acceptors."""
        print("DEBUG: GPIOPaymentThread.disable_payment() called")
        if self.gpio_available:
            self.set_acceptor_state(False)  # Disable bill acceptor
            self.set_coin_acceptor_state(False)  # Disable coin acceptor
            print("SUCCESS: Payment acceptors disabled")
        else:
            print("WARNING: GPIO not available - payment acceptors not disabled")

    def stop(self):
        """Stop the GPIO thread safely."""
        print("Stopping GPIO payment thread...")
        self.running = False

        # Give the thread a moment to finish its current iteration
        if self.isRunning():
            self.wait(1000)  # Wait up to 1 second for graceful shutdown

        if self.gpio_available and self.pi:
            try:
                self.set_acceptor_state(False)
                # Add a small delay to ensure the acceptor is properly disabled
                import time
                time.sleep(0.1)
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
    suggestion_updated = pyqtSignal(str)      # inline best payment suggestion
    amount_received_updated = pyqtSignal(float)  # amount_received
    change_updated = pyqtSignal(float, str)  # change_amount, change_text
    payment_completed = pyqtSignal(dict)  # payment_info
    go_back_requested = pyqtSignal()  # request to go back
    payment_button_enabled = pyqtSignal(bool)  # enable/disable payment button
    payment_mode_changed = pyqtSignal(bool)  # payment mode enabled/disabled

    def __init__(self, main_app=None):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.payment_algorithm = PaymentAlgorithmManager(self.db_manager)
        self.main_app = main_app
        self.total_cost = 0
        self.amount_received = 0
        self.payment_data = None
        self.cash_received = {}
        self.payment_processing = False
        self.payment_ready = False
        self.gpio_thread = None
        self.dispense_thread = None
        self.change_dispenser = ChangeDispenser()
        self.best_payment_suggestion = None  # {'amount', 'change', 'reason'}

    def set_payment_data(self, payment_data):
        """Sets the payment data and initializes payment state."""
        print(f"DEBUG: set_payment_data called with total_cost: {payment_data['total_cost']}")
        self.payment_data = payment_data
        self.total_cost = payment_data['total_cost']
        self.amount_received = 0
        self.cash_received = {}
        self.payment_ready = False
        
        # If payment screen is already active, enable payment mode now
        if hasattr(self, 'gpio_thread') and self.gpio_thread:
            print("DEBUG: Payment data set, enabling payment mode now")
            self.enable_payment_mode()

        # Extract print-related attributes for later use
        if 'pdf_data' in payment_data and 'path' in payment_data['pdf_data']:
            self.print_file_path = payment_data['pdf_data']['path']
        if 'selected_pages' in payment_data:
            self.selected_pages = payment_data['selected_pages']
        if 'copies' in payment_data:
            self.copies = payment_data['copies']
        if 'color_mode' in payment_data:
            self.color_mode = payment_data['color_mode']

        print(f"DEBUG: Print attributes set - file: {self.print_file_path}, pages: {self.selected_pages}, copies: {self.copies}, mode: {self.color_mode}")

        # Compute best payment suggestion inline based on current coin inventory
        try:
            best = self.payment_algorithm.find_best_payment_amount(self.total_cost)
            self.best_payment_suggestion = best
            # Notify UI to show suggestion inline
            self.suggestion_updated.emit(self._format_best_payment_status())
        except Exception as e:
            print(f"Error computing best payment suggestion: {e}")

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
        """Setup GPIO payment thread for payment processing."""
        print("DEBUG: setup_gpio() method called")
        # Use original GPIOPaymentThread instead of persistent GPIO
        print("DEBUG: Creating GPIOPaymentThread")
        self.gpio_thread = GPIOPaymentThread()
        print(f"DEBUG: GPIOPaymentThread created: {self.gpio_thread}")
        print(f"DEBUG: GPIO available: {self.gpio_thread.gpio_available}")

        print("DEBUG: About to connect signals")
        self.gpio_thread.coin_inserted.connect(self.on_coin_inserted)
        self.gpio_thread.bill_inserted.connect(self.on_bill_inserted)
        self.gpio_thread.payment_status.connect(self.payment_status_updated.emit)
        print("DEBUG: Signals connected successfully")

        # Start the GPIO thread
        self.gpio_thread.start()
        print("DEBUG: GPIOPaymentThread started")

    def enable_payment_mode(self):
        """Enables payment mode."""
        print(f"DEBUG: enable_payment_mode called, total_cost: {self.total_cost}")
        if self.total_cost <= 0:
            print("DEBUG: Total cost is 0 or negative, not enabling payment")
            return

        self.payment_ready = True
        print(f"DEBUG: payment_ready set to True")

        print(f"DEBUG: Checking if gpio_thread exists: {hasattr(self, 'gpio_thread')}")
        if hasattr(self, 'gpio_thread') and self.gpio_thread:
            print(f"DEBUG: gpio_thread value: {self.gpio_thread}")
            print(f"DEBUG: Calling gpio_thread.enable_payment()")
            self.gpio_thread.enable_payment()
            print("SUCCESS: Payment mode enabled via GPIOPaymentThread")
        else:
            print("ERROR: No GPIO thread available")

        status_text = "Payment mode enabled - Use simulation buttons" if not self.gpio_thread.gpio_available else "Payment mode enabled - Insert coins or bills"
        self.payment_status_updated.emit(status_text)
        self.payment_mode_changed.emit(True)

    def disable_payment_mode(self):
        """Disables payment mode."""
        self.payment_ready = False
        if hasattr(self, 'gpio_thread') and self.gpio_thread:
            self.gpio_thread.disable_payment()
            print("SUCCESS: Payment mode disabled via GPIOPaymentThread")
        else:
            print("ERROR: No GPIO thread available")

        status_text = "Payment mode disabled" + (" (Simulation)" if not (hasattr(self, 'gpio_thread') and self.gpio_thread and self.gpio_thread.gpio_available) else "")
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
        self.payment_status_updated.emit(f"P{coin_value} coin received")

    def on_bill_inserted(self, bill_value):
        """Handles bill insertion."""
        if not self.payment_ready:
            return

        self.amount_received += bill_value
        self.cash_received[bill_value] = self.cash_received.get(bill_value, 0) + 1
        self.amount_received_updated.emit(self.amount_received)
        self._update_payment_status()
        self.payment_status_updated.emit(f"P{bill_value} bill received")

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
        try:
            # Prevent multiple automatic completions
            if hasattr(self, '_payment_completing') and self._payment_completing:
                print("WARNING: Payment already completing, ignoring duplicate trigger")
                return

            if self.amount_received >= self.total_cost and self.total_cost > 0:
                change = self.amount_received - self.total_cost
                change_text = f"Payment Complete. Change: P{change:.2f}" if change > 0 else "Payment Complete"
                self.change_updated.emit(change, change_text)
                self.payment_button_enabled.emit(True)  # Enable payment button when sufficient payment

                if self.payment_ready and not (hasattr(self, '_payment_completing') and self._payment_completing):
                    self._payment_completing = True  # Prevent duplicate processing
                    self.payment_status_updated.emit("Payment sufficient - Processing automatically...")
                    self.disable_payment_mode()
                    # Automatically proceed to payment completion
                    self._auto_complete_payment()
            else:
                remaining = self.total_cost - self.amount_received
                change_text = f"Remaining: P{remaining:.2f}"
                self.change_updated.emit(0, change_text)
                self.payment_button_enabled.emit(False)  # Disable payment button when insufficient payment

        except Exception as e:
            print(f"ERROR: Error in payment status update: {e}")
            self.payment_status_updated.emit(f"Payment error: {str(e)}")

        # Refresh inline suggestion each time status updates
        try:
            best = self.payment_algorithm.find_best_payment_amount(self.total_cost)
            self.best_payment_suggestion = best
            self.suggestion_updated.emit(self._format_best_payment_status())
        except Exception as e:
            print(f"Error refreshing best payment suggestion: {e}")

    def _format_best_payment_status(self) -> str:
        if not self.best_payment_suggestion:
            return ""
        amt = self.best_payment_suggestion.get('amount', self.total_cost)
        chg = self.best_payment_suggestion.get('change', 0)
        if chg == 0:
            return f"Max payment we can receive: P{amt:.2f} (exact)"
        return f"Max payment we can receive: P{amt:.2f} (available P{chg:.2f})"

    def _auto_complete_payment(self):
        """Automatically complete payment when sufficient amount is received."""
        print("Auto-completing payment...")

        # Show processing message
        self.payment_status_updated.emit("Dispensing change and preparing to print...")

        # Add a small delay to show the processing message
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(1500, self._proceed_with_payment)

    def _proceed_with_payment(self):
        """Proceed with payment completion after delay."""
        print("Proceeding with payment completion...")

        # Check if we have main_app reference
        if hasattr(self, 'main_app') and self.main_app:
            # Call the existing complete_payment method
            success, message = self.complete_payment(self.main_app)
            if success:
                print("SUCCESS: Auto-payment completion successful")
            else:
                print(f"ERROR: Auto-payment completion failed: {message}")
                self.payment_status_updated.emit(f"Payment error: {message}")
        else:
            print("ERROR: No main_app reference available for auto-payment completion")
            self.payment_status_updated.emit("Payment completion failed - no app reference")

    def _check_payment_capabilities(self):
        """Check payment capabilities and emit suggestions to UI."""
        try:
            # Get payment suggestions
            suggestions = self.payment_algorithm.find_optimal_payment_amounts(self.total_cost)
            status_message = self.payment_algorithm.get_payment_status_message(self.total_cost)

            # Emit payment suggestions to UI
            self.payment_status_updated.emit(status_message)

            # Store suggestions for UI to display
            self.payment_suggestions = suggestions

            print(f"Payment capabilities checked. Status: {status_message}")
            print(f"Found {len(suggestions)} payment suggestions")

        except Exception as e:
            print(f"Error checking payment capabilities: {e}")
            self.payment_status_updated.emit("Error checking payment capabilities")

    def validate_payment_amount(self, payment_amount: float) -> Tuple[bool, str]:
        """Validate if a payment amount can be processed."""
        return self.payment_algorithm.validate_payment(self.total_cost, payment_amount)

    def get_payment_suggestions(self) -> List[Dict]:
        """Get payment suggestions for the current total cost."""
        return self.payment_algorithm.find_optimal_payment_amounts(self.total_cost)


    def log_transaction_after_print_success(self):
        """Log the transaction to database after successful printing."""
        print(f"DEBUG: Payment model log_transaction_after_print_success called")
        print(f"DEBUG: hasattr transaction_data: {hasattr(self, 'transaction_data')}")
        if hasattr(self, 'transaction_data'):
            print(f"DEBUG: transaction_data value: {self.transaction_data}")

        # Transaction is already logged when payment completes, so just update status if needed
        if hasattr(self, 'transaction_data') and self.transaction_data:
            print(f"✅ Transaction already logged during payment completion: {self.transaction_data['file_name']}")
            # Optionally update status to 'printed' if you want to track print completion
            # self.transaction_data['status'] = 'printed'
        else:
            print("⚠️ No transaction data available to log")

    # Print job signals are now handled by the thank you screen
    # No need to connect them here since the thank you screen will manage the entire print lifecycle

    def _on_dispensing_finished(self, result):
        """Handles the completion of change dispensing."""
        print(f"DEBUG: _on_dispensing_finished called with result={result}")

        try:
            if isinstance(result, dict) and result.get('success', False):
                # New flow: Update database with actual coins dispensed, then print
                coins_1 = result.get('coins_1', 0)
                coins_5 = result.get('coins_5', 0)
                actual_change = result.get('actual_change', 0)
                expected_change = result.get('expected_change', 0)

                print(f"DEBUG: Change dispensing completed - P1={coins_1}, P5={coins_5}, actual={actual_change}, expected={expected_change}")
                self.payment_status_updated.emit(f"Change dispensed! Updating inventory...")

                # Store dispensed change data for later database update
                self.change_dispensed = {1: coins_1, 5: coins_5}
                print(f"DEBUG: Stored dispensed change data: {self.change_dispensed}")

                # Update database immediately when coins are dispensed
                if coins_1 > 0 or coins_5 > 0:
                    print(f"DEBUG: Updating database immediately with dispensed coins: P1={coins_1}, P5={coins_5}")
                    self._update_coin_inventory_immediately(coins_1, coins_5)
                    # Prevent double subtraction later in the post-print step
                    self.change_dispensed = None
                    print("DEBUG: change_dispensed cleared after immediate decrement to avoid double subtraction")

                print("DEBUG: Change dispensing completed, proceeding to print")
                self._start_printing()
            else:
                # Fallback for old boolean format
                print(f"DEBUG: Old format result: {result}")
                if result:
                    print("Dispensing complete.")
                    self._start_printing()
                else:
                    print("CRITICAL: Error dispensing change.")
                    self._navigate_to_thank_you()
        except Exception as e:
            print(f"ERROR: Exception in _on_dispensing_finished: {e}")
            # Fallback to navigation even if there's an error
            self._navigate_to_thank_you()

        # Clean up change dispenser after dispensing is complete
        try:
            if hasattr(self, 'change_dispenser') and self.change_dispenser:
                print("DEBUG: Cleaning up change dispenser after dispensing complete")
                self.change_dispenser.cleanup()
                # Don't set to None here as it might be needed for future transactions
        except Exception as e:
            print(f"DEBUG: Error cleaning up change dispenser: {e}")

        # Clean up the dispense thread
        try:
            if hasattr(self, 'dispense_thread') and self.dispense_thread:
                print("DEBUG: Cleaning up dispense thread after completion")
                if self.dispense_thread.isRunning():
                    self.dispense_thread.terminate()
                    self.dispense_thread.wait(1000)
                self.dispense_thread = None
        except Exception as e:
            print(f"DEBUG: Error cleaning up dispense thread: {e}")



    # Print job success/failure handling is now done by the thank you screen
    # The thank you screen will monitor lpstat and handle print completion

    # Print timeout handling is now done by the thank you screen
    # The thank you screen will handle all print job monitoring and timeouts

    def _update_coin_inventory_immediately(self, coins_1, coins_5):
        """Update coin inventory immediately when coins are dispensed."""
        try:
            print(f"DEBUG: Updating coin inventory immediately - P1: {coins_1}, P5: {coins_5}")

            # Get current inventory
            inventory = self.db_manager.get_cash_inventory()
            current_1 = 0
            current_5 = 0

            for item in inventory:
                if item['denomination'] == 1 and item['type'] == 'coin':
                    current_1 = item['count']
                elif item['denomination'] == 5 and item['type'] == 'coin':
                    current_5 = item['count']

            # Calculate new counts (prevent negative)
            new_1 = max(0, current_1 - coins_1)
            new_5 = max(0, current_5 - coins_5)

            # Update database
            self.db_manager.update_cash_inventory(1, new_1, 'coin')
            self.db_manager.update_cash_inventory(5, new_5, 'coin')

            print(f"✅ Coin inventory updated immediately: P1 {current_1} -> {new_1}, P5 {current_5} -> {new_5}")

        except Exception as e:
            print(f"❌ Error updating coin inventory immediately: {e}")

    def _navigate_to_thank_you(self):
        """Navigate to thank you screen after all operations are complete."""
        print("DEBUG: _navigate_to_thank_you called")
        print("DEBUG: Current thread:", threading.current_thread().name)
        print("DEBUG: main_app available:", hasattr(self, 'main_app') and self.main_app is not None)

        try:
            # Emit payment completed signal now that everything is done
            if hasattr(self, 'payment_info') and self.payment_info:
                print("DEBUG: Emitting payment_completed signal with stored payment info")
                self.payment_completed.emit(self.payment_info)
            else:
                print("DEBUG: No payment info available to emit")

            if hasattr(self, 'main_app') and self.main_app:
                print("DEBUG: Navigating to thank you screen")
                self.main_app.show_screen('thank_you')
                print("DEBUG: Navigation to thank you screen completed")
            else:
                print("DEBUG: No main_app available for navigation")
        except Exception as e:
            print(f"ERROR: Exception in _navigate_to_thank_you: {e}")
            # Try to navigate anyway as a fallback
            try:
                if hasattr(self, 'main_app') and self.main_app:
                    self.main_app.show_screen('thank_you')
            except Exception as fallback_error:
                print(f"ERROR: Fallback navigation also failed: {fallback_error}")

    def on_enter(self):
        """Called when the payment screen is shown."""
        print("=== PAYMENT MODEL ON_ENTER START ===")
        print("Payment screen entered")
        print("DEBUG: About to call setup_gpio()")
        try:
            self.setup_gpio()
            print("DEBUG: setup_gpio() completed successfully")
        except Exception as e:
            print(f"DEBUG: setup_gpio() failed with error: {e}")

        # Reset payment state
        self.amount_received = 0
        self.cash_received = {}
        self.payment_processing = False

        self.amount_received_updated.emit(0)
        self.change_updated.emit(0, "")

        # Automatically enable payment mode
        print("DEBUG: About to call enable_payment_mode()")
        self.enable_payment_mode()
        print("=== PAYMENT MODEL ON_ENTER END ===")

    def on_leave(self):
        """Called when leaving the payment screen."""
        print("=== PAYMENT MODEL ON_LEAVE START ===")
        print("Payment screen leaving")

        # Stop and cleanup GPIO thread
        if hasattr(self, 'gpio_thread') and self.gpio_thread:
            print("DEBUG: About to stop GPIOPaymentThread")
            self.gpio_thread.stop()
            if self.gpio_thread.isRunning():
                self.gpio_thread.wait(2000)  # Wait up to 2 seconds for graceful shutdown
            print("DEBUG: GPIOPaymentThread stopped")
        else:
            print("ERROR: No GPIO thread available to stop")
        print("Payment screen cleanup completed")

        # Stop any running dispense thread
        if hasattr(self, 'dispense_thread') and self.dispense_thread:
            print("Stopping dispense thread...")
            try:
                if self.dispense_thread.isRunning():
                    self.dispense_thread.terminate()
                    self.dispense_thread.wait(1000)
            except Exception as e:
                print(f"Error stopping dispense thread: {e}")
            finally:
                # Clear the thread reference
                self.dispense_thread = None

        # Clean up change dispenser if it exists and is not being used
        if hasattr(self, 'change_dispenser') and self.change_dispenser:
            # Check if there's an active dispense thread
            if hasattr(self, 'dispense_thread') and self.dispense_thread and self.dispense_thread.isRunning():
                print("Payment screen: Skipping change dispenser cleanup - dispense thread still running")
            else:
                try:
                    print("Cleaning up change dispenser...")
                    self.change_dispenser.cleanup()
                except Exception as e:
                    print(f"Error cleaning up change dispenser: {e}")
                finally:
                    self.change_dispenser = None

    def _log_partial_payment(self):
        """Log partial payment when user cancels transaction."""
        try:
            if not (self.amount_received and self.payment_data):
                return

            # Defensive guards for keys
            pdf_data = self.payment_data.get('pdf_data') or {}
            file_path = pdf_data.get('path') or "unknown.pdf"
            selected_pages = self.payment_data.get('selected_pages') or []
            copies = int(self.payment_data.get('copies') or 1)
            color_mode = self.payment_data.get('color_mode') or 'Color'

            # Log cancelled transaction with partial payment
            transaction_data = {
                'file_name': os.path.basename(file_path),
                'pages': len(selected_pages),
                'copies': copies,
                'color_mode': color_mode,
                'total_cost': float(self.total_cost or 0),
                'amount_paid': float(self.amount_received or 0),
                'change_given': 0,  # No change given since transaction cancelled
                'status': 'cancelled_partial_payment'
            }
            try:
                self.db_manager.log_transaction(transaction_data)
            except Exception as log_err:
                print(f"WARNING: Failed to log cancelled transaction: {log_err}")

            # Safely increment cash inventory with received money (do not overwrite totals)
            try:
                current_inventory = {}
                for item in (self.db_manager.get_cash_inventory() or []):
                    if item.get('type') == 'coin' or item.get('type') == 'bill':
                        current_inventory[(item.get('type'), int(item.get('denomination')))] = int(item.get('count') or 0)

                for denomination, count in (self.cash_received or {}).items():
                    if not count:
                        continue
                    is_bill = denomination >= 20
                    key = ('bill' if is_bill else 'coin', int(denomination))
                    new_count = current_inventory.get(key, 0) + int(count)
                    self.db_manager.update_cash_inventory(
                        denomination=int(denomination),
                        count=new_count,
                        type='bill' if is_bill else 'coin'
                    )
            except Exception as inv_err:
                print(f"WARNING: Failed to update cash inventory on cancel: {inv_err}")

            print(f"Logged cancelled transaction: {self.amount_received} received, {self.total_cost} required")
        except Exception as e:
            print(f"WARNING: _log_partial_payment encountered an error but will not block navigation: {e}")

    def complete_payment(self, main_app):
        """Complete the payment process - dispense change and start printing."""
        print("Starting payment completion process...")
        print(f"DEBUG: Payment completion - amount_received: {self.amount_received}, total_cost: {self.total_cost}")

        try:
            # Validate payment data exists
            if not hasattr(self, 'payment_data') or self.payment_data is None:
                print("ERROR: No payment data available")
                return False, "No payment data available"

            # Validate main_app reference
            if not main_app:
                print("ERROR: No main app reference")
                return False, "No main app reference"

            # Calculate change to dispense
            change_amount = self.amount_received - self.total_cost
            print(f"Change to dispense: P{change_amount:.2f}")
            print(f"DEBUG: Payment calculation - received: {self.amount_received}, cost: {self.total_cost}, change: {change_amount}")

            # Create transaction data and log immediately so it exists regardless of print outcome
            try:
                pdf_path = None
                selected_pages = []
                copies = 1
                color_mode = 'Color'

                if hasattr(self, 'payment_data') and self.payment_data:
                    pdf_info = self.payment_data.get('pdf_data') or {}
                    pdf_path = pdf_info.get('path')
                    selected_pages = self.payment_data.get('selected_pages') or []
                    copies = int(self.payment_data.get('copies') or 1)
                    color_mode = self.payment_data.get('color_mode') or 'Color'

                file_name = os.path.basename(pdf_path) if pdf_path else 'unknown.pdf'

                self.transaction_data = {
                    'file_name': file_name,
                    'pages': len(selected_pages),
                    'copies': copies,
                    'color_mode': color_mode,
                    'total_cost': float(self.total_cost or 0),
                    'amount_paid': float(self.amount_received or 0),
                    'change_given': float(change_amount or 0),
                    'status': 'completed'
                }
                print(f"DEBUG: Transaction data (late path) created: {self.transaction_data}")
                try:
                    self.db_manager.log_transaction(self.transaction_data)
                    print(f"✅ Transaction logged immediately (late path): {self.transaction_data['file_name']}")
                except Exception as log_err:
                    print(f"❌ Error logging transaction immediately (late path): {log_err}")
            except Exception as tx_err:
                print(f"❌ Error creating transaction data (late path): {tx_err}")

            # Stop any existing dispense thread to prevent conflicts
            if hasattr(self, 'dispense_thread') and self.dispense_thread and self.dispense_thread.isRunning():
                print("WARNING: Stopping existing dispense thread")
                self.dispense_thread.terminate()
                self.dispense_thread.wait(1000)
                self.dispense_thread = None

            # Create change dispenser if not exists
            if not hasattr(self, 'change_dispenser') or self.change_dispenser is None:
                from managers.hopper_manager import ChangeDispenser
                self.change_dispenser = ChangeDispenser()
                print("SUCCESS: Change dispenser created")

            # Start dispensing change in a separate thread
            if change_amount > 0:
                print(f"Starting change dispensing for P{change_amount:.2f}")
                # Compute required coins using payment algorithm (respects inventory)
                can_dispense, reason, required_coins = self.payment_algorithm.can_dispense_change(change_amount)
                if not can_dispense:
                    print(f"WARNING: Algorithm reports change not dispensable: {reason}. Proceeding with best-effort greedy.")
                    required_coins = None

                self.dispense_thread = DispenseThread(
                    dispenser=self.change_dispenser,
                    amount=change_amount,
                    admin_screen=main_app.admin_screen,
                    db_threader=main_app.db_threader,
                    required_coins=required_coins
                )
                self.dispense_thread.status_update.connect(self.payment_status_updated.emit)
                self.dispense_thread.dispensing_finished.connect(self._on_dispensing_finished)
                self.dispense_thread.start()
                print("SUCCESS: Dispense thread started")
            else:
                # No change to dispense, proceed directly to printing
                print("SUCCESS: No change to dispense, proceeding to printing")
                self._start_printing()

            return True, "Payment processing started"

        except Exception as e:
            print(f"ERROR: Error in payment completion: {e}")
            # Reset payment completing flag on error
            if hasattr(self, '_payment_completing'):
                self._payment_completing = False
            return False, f"Payment completion failed: {str(e)}"

    def _start_printing(self):
        """Start the printing process."""
        print("Starting printing process...")

        try:
            # Validate payment data exists
            if not hasattr(self, 'payment_data') or not self.payment_data:
                print("ERROR: No payment data available for printing")
                self.payment_status_updated.emit("No payment data available for printing")
                return

            # Validate main app reference
            if not hasattr(self, 'main_app') or not self.main_app:
                print("ERROR: No main app reference for printing")
                self.payment_status_updated.emit("No main app reference for printing")
                return

            # Validate PDF data exists
            if 'pdf_data' not in self.payment_data or not self.payment_data['pdf_data']:
                print("ERROR: No PDF data available for printing")
                self.payment_status_updated.emit("No PDF data available for printing")
                return

            # Store print job details in main app for thank you screen
            print_job_details = {
                'file_path': self.payment_data['pdf_data']['path'],
                'selected_pages': self.payment_data.get('selected_pages', [1]),
                'copies': self.payment_data.get('copies', 1),
                'color_mode': self.payment_data.get('color_mode', 'Color')
            }
            self.main_app.current_print_job = print_job_details
            print(f"SUCCESS: Print job details stored: {print_job_details}")

            # Navigate to thank you screen
            self._navigate_to_thank_you()

        except Exception as e:
            print(f"ERROR: Error starting printing: {e}")
            self.payment_status_updated.emit(f"Printing error: {str(e)}")
            # Try to navigate to thank you screen anyway
            try:
                self._navigate_to_thank_you()
            except Exception as nav_error:
                print(f"ERROR: Error navigating to thank you screen: {nav_error}")


    def reset_payment_state(self):
        """Reset payment state for new transactions."""
        print("Resetting payment state...")

        try:
            # Reset payment completing flag
            if hasattr(self, '_payment_completing'):
                self._payment_completing = False

            # Reset payment amounts
            self.amount_received = 0
            self.total_cost = 0
            self.cash_received = {}

            # Reset payment data
            self.payment_data = None

            # Stop any running dispense thread
            if hasattr(self, 'dispense_thread') and self.dispense_thread and self.dispense_thread.isRunning():
                print("WARNING: Stopping dispense thread during reset")
                self.dispense_thread.terminate()
                self.dispense_thread.wait(1000)
                self.dispense_thread = None

            # Reset payment ready state
            self.payment_ready = False

            # Emit reset signals
            self.amount_received_updated.emit(0)
            self.change_updated.emit(0, "")
            self.payment_status_updated.emit("Payment screen ready")

            print("SUCCESS: Payment state reset complete")

        except Exception as e:
            print(f"ERROR: Error resetting payment state: {e}")

    def go_back(self):
        """Goes back to print options screen."""
        print("Payment screen: going back to print options")

        # Only log partial payment if user received cash but amount was insufficient
        if self.amount_received > 0 and self.amount_received < self.total_cost:
            print(f"DEBUG: Logging partial payment - received {self.amount_received}, required {self.total_cost}")
            self._log_partial_payment()
        elif self.amount_received >= self.total_cost:
            print(f"DEBUG: Payment was sufficient ({self.amount_received} >= {self.total_cost}), not logging as cancelled")
        else:
            print("DEBUG: No payment received, not logging transaction")

        self.on_leave()
        self.reset_payment_state()
        self.go_back_requested.emit()
