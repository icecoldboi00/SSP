import os
import time
import threading
from typing import Tuple, List, Dict
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QTimer
from managers.hopper_manager import ChangeDispenser, DispenseThread, PIGPIO_AVAILABLE as HOPPER_GPIO_AVAILABLE
from managers.payment_algorithm_manager import PaymentAlgorithmManager
from database.db_manager import DatabaseManager
from managers.payment_handler import get_payment_handler, cleanup_payment_handler


class PaymentGPIOController(QObject):
    """Simplified GPIO controller using the new payment handler."""
    coin_inserted = pyqtSignal(int)
    special_coin_inserted = pyqtSignal(int)  # Special coins that cannot be given as change
    bill_inserted = pyqtSignal(int)
    payment_status = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.payment_handler = None
        self.initialized = False
    
    def initialize(self):
        """Initialize the payment handler."""
        try:
            # Clean up any existing handler first
            cleanup_payment_handler()
            
            self.payment_handler = get_payment_handler()
            if self.payment_handler:
                # Debug: Check if the special_coin_inserted signal exists
                if hasattr(self.payment_handler, 'special_coin_inserted'):
                    print("PaymentGPIOController: special_coin_inserted signal found")
                else:
                    print("PaymentGPIOController: ERROR - special_coin_inserted signal NOT found!")
                    print(f"PaymentGPIOController: Available signals: {[attr for attr in dir(self.payment_handler) if 'Signal' in str(type(getattr(self.payment_handler, attr, None)))]}")
                
                # Connect signals
                self.payment_handler.coin_inserted.connect(self.coin_inserted.emit)
                self.payment_handler.special_coin_inserted.connect(self.special_coin_inserted.emit)
                self.payment_handler.bill_inserted.connect(self.bill_inserted.emit)
                self.payment_handler.payment_status.connect(self.payment_status.emit)
                
                self.initialized = True
                print("PaymentGPIOController: Initialized successfully")
                return True
            else:
                print("PaymentGPIOController: Failed to get payment handler")
                return False
        except Exception as e:
            print(f"PaymentGPIOController: Initialization failed - {e}")
            return False
    
    def enable_payments(self):
        """Enable payment acceptors."""
        if self.payment_handler and self.initialized:
            return self.payment_handler.enable_payments()
        return False
    
    def disable_payments(self):
        """Disable payment acceptors."""
        if self.payment_handler and self.initialized:
            return self.payment_handler.disable_payments()
        return False
    
    def get_status(self):
        """Get payment handler status."""
        if self.payment_handler and self.initialized:
            return self.payment_handler.get_status()
        return {'initialized': False}
    
    def cleanup(self):
        """Clean up resources."""
        if self.payment_handler:
            self.payment_handler.cleanup()
            self.payment_handler = None
        self.initialized = False

    


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
        self.gpio_controller = None
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
        
        # Always enable payment mode when payment data is set
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
        """Setup GPIO controller for payment processing."""
        print("DEBUG: setup_gpio() method called")
        
        # Create and initialize GPIO controller
        self.gpio_controller = PaymentGPIOController()
        print("DEBUG: PaymentGPIOController created")
        
        # Initialize the controller
        if self.gpio_controller.initialize():
            print("DEBUG: GPIO controller initialized successfully")
            
            # Connect signals
            self.gpio_controller.coin_inserted.connect(self.on_coin_inserted)
            self.gpio_controller.special_coin_inserted.connect(self.on_special_coin_inserted)
            self.gpio_controller.bill_inserted.connect(self.on_bill_inserted)
            self.gpio_controller.payment_status.connect(self.payment_status_updated.emit)
            print("DEBUG: Signals connected successfully")
            
            # Set initial payment status
            self.payment_status_updated.emit("Payment system ready - Coin and bill acceptors disabled")
        else:
            print("WARNING: GPIO controller initialization failed - payment will use simulation mode")
            self.gpio_controller = None

    def enable_payment_mode(self):
        """Enables payment mode using the new payment handler."""
        print(f"DEBUG: enable_payment_mode called, total_cost: {self.total_cost}")
        if self.total_cost <= 0:
            print("DEBUG: Total cost is 0 or negative, not enabling payment")
            return

        self.payment_ready = True
        print(f"DEBUG: payment_ready set to True")

        # Enable payments using the new controller
        if self.gpio_controller and self.gpio_controller.initialized:
            if self.gpio_controller.enable_payments():
                print("SUCCESS: Payment acceptors enabled via new payment handler")
                status_text = "Payment mode enabled - Insert coins or bills"
            else:
                print("WARNING: Failed to enable payments via controller")
                status_text = "Payment mode enabled - Use simulation buttons"
        else:
            print("WARNING: GPIO controller not available")
            status_text = "Payment mode enabled - Use simulation buttons"

        # Emit status update
        self.payment_status_updated.emit(status_text)
        self.payment_mode_changed.emit(True)

    def disable_payment_mode(self):
        """Disables payment mode using the new payment handler."""
        self.payment_ready = False
        
        # Disable payments using the new controller
        if self.gpio_controller and self.gpio_controller.initialized:
            if self.gpio_controller.disable_payments():
                print("SUCCESS: Payment acceptors disabled via new payment handler")
            else:
                print("WARNING: Failed to disable payments via controller")
        else:
            print("WARNING: GPIO controller not available")

        status_text = "Payment mode disabled"
        self.payment_status_updated.emit(status_text)
        self.payment_mode_changed.emit(False)
    
    def test_gpio_connection(self):
        """Test GPIO connection and return status."""
        try:
            import pigpio
            pi = pigpio.pi()
            if pi.connected:
                print("✅ GPIO connection test successful")
                pi.stop()
                return True
            else:
                print("❌ GPIO connection test failed - not connected")
                return False
        except Exception as e:
            print(f"❌ GPIO connection test failed: {e}")
            return False

    def on_coin_inserted(self, coin_value):
        """Handles coin insertion."""
        print(f"DEBUG: on_coin_inserted called with value: {coin_value}")
        print(f"DEBUG: payment_ready: {self.payment_ready}")
        if not self.payment_ready:
            print("DEBUG: Payment not ready, ignoring coin")
            return

        print(f"DEBUG: Processing coin - value: {coin_value}")
        self.amount_received += coin_value
        self.cash_received[coin_value] = self.cash_received.get(coin_value, 0) + 1
        print(f"DEBUG: Amount received updated to: {self.amount_received}")
        print(f"DEBUG: Total cost: {self.total_cost}")
        print(f"DEBUG: Remaining: {self.total_cost - self.amount_received}")
        
        # Emit signals to update UI
        self.amount_received_updated.emit(self.amount_received)
        self._update_payment_status()
        self.payment_status_updated.emit(f"P{coin_value} coin received")
        
        print("DEBUG: UI signals emitted successfully")
    
    def on_special_coin_inserted(self, coin_value):
        """Handles special coin insertion (coins that cannot be given as change)."""
        print(f"DEBUG: on_special_coin_inserted called with value: {coin_value}")
        print(f"DEBUG: payment_ready: {self.payment_ready}")
        if not self.payment_ready:
            print("DEBUG: Payment not ready, ignoring special coin")
            return

        print(f"DEBUG: Processing special coin - value: {coin_value} (will not be added to inventory)")
        self.amount_received += coin_value
        # Note: We don't add special coins to cash_received since they won't be added to database inventory
        print(f"DEBUG: Amount received updated to: {self.amount_received}")
        print(f"DEBUG: Total cost: {self.total_cost}")
        print(f"DEBUG: Remaining: {self.total_cost - self.amount_received}")
        
        # Emit signals to update UI
        self.amount_received_updated.emit(self.amount_received)
        self._update_payment_status()
        self.payment_status_updated.emit(f"P{coin_value} special coin received (not added to inventory)")
        
        print("DEBUG: Special coin UI signals emitted successfully")
    

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
                # Reset the flag if payment failed
                self._payment_completing = False
        else:
            print("ERROR: No main_app reference available for auto-payment completion")
            self.payment_status_updated.emit("Payment completion failed - no app reference")
            # Reset the flag if no main_app reference
            self._payment_completing = False

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
        self._payment_completing = False  # Reset payment completion flag

        self.amount_received_updated.emit(0)
        self.change_updated.emit(0, "")

        # Automatically enable payment mode if we have valid payment data
        if hasattr(self, 'total_cost') and self.total_cost > 0:
            print("DEBUG: About to call enable_payment_mode()")
            self.enable_payment_mode()
        else:
            print("DEBUG: No valid payment data yet, payment mode will be enabled when data is set")
        print("=== PAYMENT MODEL ON_ENTER END ===")

    def on_leave(self):
        """Called when leaving the payment screen."""
        print("=== PAYMENT MODEL ON_LEAVE START ===")
        print("Payment screen leaving")

        # Disable payment mode and coin acceptor
        print("DEBUG: Disabling payment mode...")
        self.disable_payment_mode()

        # Stop and cleanup GPIO controller
        if hasattr(self, 'gpio_controller') and self.gpio_controller:
            print("DEBUG: About to cleanup GPIO controller")
            self.gpio_controller.cleanup()
            self.gpio_controller = None
            print("DEBUG: GPIO controller cleaned up")
        else:
            print("DEBUG: No GPIO controller to cleanup")
        
        # Clean up global payment handler to prevent conflicts
        print("DEBUG: Cleaning up global payment handler")
        cleanup_payment_handler()
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
