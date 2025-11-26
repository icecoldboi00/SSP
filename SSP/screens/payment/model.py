import os
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from managers.hopper_manager import ChangeDispenser, DispenseThread
from managers.payment_algorithm_manager import PaymentAlgorithmManager
from database.db_manager import DatabaseManager
from managers.payment_handler import get_payment_handler, cleanup_payment_handler


class PaymentModel(QObject):
    payment_data_updated = pyqtSignal(dict)  # payment_data
    payment_status_updated = pyqtSignal(str)  # status_message
    suggestion_updated = pyqtSignal(str)      # inline best payment suggestion
    amount_received_updated = pyqtSignal(float)  # amount_received
    change_updated = pyqtSignal(float, str)  # change_amount, change_text
    payment_completed = pyqtSignal(dict)  # payment_info passed to main
    go_back_requested = pyqtSignal()  # request to go back
    payment_mode_changed = pyqtSignal(bool)  # payment mode enabled/disabled

    def __init__(self, main_app):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.payment_algorithm = PaymentAlgorithmManager(self.db_manager) #Same db_manager instance
        self.change_dispenser = ChangeDispenser()
        self.main_app = main_app

        self.total_cost = 0
        self.amount_received = 0
        self.payment_data = None
        self.cash_received = {}
        self.payment_ready = False
        self._payment_completing = False  # Prevent duplicate payment completions

        self.payment_handler = None
        self.dispense_thread = None
        self.best_payment_suggestion = None  # {'amount', 'change', 'reason'}

    def set_payment_data(self, payment_data):
        self.payment_data = payment_data
        self.total_cost = payment_data['total_cost']
        self.amount_received = 0
        self.cash_received = {}
        self.payment_ready = False
        
        # Always enable payment mode when payment data is set
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

        # Compute best payment suggestion inline based on current coin inventory
        best = self.payment_algorithm.find_best_payment_amount(self.total_cost)
        self.best_payment_suggestion = best
        self.suggestion_updated.emit(self._format_best_payment_status())


        # Prepare summary data for UI
        doc_name = os.path.basename(payment_data['pdf_data']['path'])

        summary_data = {
            'total_cost': self.total_cost,
            'document_name': doc_name,
            'copies': payment_data['copies'],
            'color_mode': payment_data['color_mode']
        }

        self.payment_data_updated.emit(summary_data)

    def setup_gpio(self):
        cleanup_payment_handler()
        
        # Create instance and start listening for pulses
        self.payment_handler = get_payment_handler()
        if self.payment_handler:
            # Connect signals directly from PaymentHandler
            self.payment_handler.coin_inserted.connect(self.on_coin_inserted)
            self.payment_handler.special_coin_inserted.connect(self.on_special_coin_inserted)
            self.payment_handler.bill_inserted.connect(self.on_bill_inserted)
            self.payment_handler.payment_status.connect(self.payment_status_updated.emit)
            
            # Set initial payment status
            self.payment_status_updated.emit("Payment system ready - Coin and bill acceptors disabled")
        else:
            print(" broken")
            self.payment_handler = None

    def enable_payment_mode(self):
        if self.total_cost <= 0:
            return

        self.payment_ready = True

        # Enable payments using PaymentHandler directly
        if self.payment_handler:
            if self.payment_handler.enable_payments():
                status_text = ""
            else:
                status_text = "Hardware broken"
        else:
            status_text = "Hardware broken"

        # Emit status update
        if status_text:  # Only emit if there's an error message
            self.payment_status_updated.emit(status_text)
        self.payment_mode_changed.emit(True)

    def disable_payment_mode(self):
        self.payment_ready = False
        
        if self.payment_handler:
            self.payment_handler.disable_payments()

        status_text = "Payment mode disabled"
        self.payment_status_updated.emit(status_text)
        self.payment_mode_changed.emit(False)

    def on_coin_inserted(self, coin_value):
        if not self.payment_ready:
            return

        self.amount_received += coin_value
        self.cash_received[coin_value] = self.cash_received.get(coin_value, 0) + 1
        
        self.amount_received_updated.emit(self.amount_received)
        self._update_payment_status()
    
    def on_special_coin_inserted(self, coin_value):
        if not self.payment_ready:
            return

        self.amount_received += coin_value
        # Note: We don't add special coins to cash_received since they won't be added to database inventory
        
        # Emit signals to update UI
        self.amount_received_updated.emit(self.amount_received)
        self._update_payment_status()
        
    def on_bill_inserted(self, bill_value):
        if not self.payment_ready:
            return

        self.amount_received += bill_value
        self.amount_received_updated.emit(self.amount_received)
        self._update_payment_status()

    def _update_payment_status(self): # Everytime a coin or bill is inserted this is called
        try:
            # Prevent multiple automatic completions
            if self._payment_completing:
                return

            if self.amount_received >= self.total_cost and self.total_cost > 0:
                change = self.amount_received - self.total_cost
                change_text = f"Payment Complete. Change: P{change:.2f}" if change > 0 else "Payment Complete"
                self.change_updated.emit(change, change_text)

                if self.payment_ready and not self._payment_completing:
                    self._payment_completing = True  # Prevent duplicate processing
                    self.payment_status_updated.emit("Payment sufficient")
                    self.disable_payment_mode() # Disable acceptors
                    self._auto_complete_payment()
            else:
                remaining = self.total_cost - self.amount_received
                change_text = f"Remaining: P{remaining:.2f}"
                self.change_updated.emit(0, change_text)

        except Exception as e:
            self.payment_status_updated.emit(f"Payment error: {str(e)}")

    def _format_best_payment_status(self) -> str:
        if not self.best_payment_suggestion:
            return ""
        amt = self.best_payment_suggestion.get('amount', self.total_cost)
        chg = self.best_payment_suggestion.get('change', 0)
        if chg == 0:
            return "Please pay in EXACT AMOUNT. No available change."
        return f"Max payment we can receive: P{amt:.2f} (available P{chg:.2f})"

    def _auto_complete_payment(self):
        self.payment_status_updated.emit("Dispensing change please wait...")

        QTimer.singleShot(1500, self._proceed_with_payment) # 1.5 seconds delay before proceeding with payment

    def _proceed_with_payment(self):
        success, message = self.complete_payment()
        if not success:
            print(f"Payment completion failed: {message}")
            self.payment_status_updated.emit(f"Payment error: {message}")
            # Reset the flag if payment failed
            self._payment_completing = False

    def log_transaction(self, payment_info):
        try:
            print(f"Logging transaction")
            # Extract transaction data
            pdf_data = payment_info.get('pdf_data', {})
            file_path = pdf_data.get('path', 'unknown.pdf')
            selected_pages = payment_info.get('selected_pages', [])
            
            transaction_data = {
                'file_name': os.path.basename(file_path),
                'pages': len(selected_pages),
                'copies': payment_info.get('copies', 1),
                'color_mode': payment_info.get('color_mode', 'Color'),
                'total_cost': payment_info.get('total_cost', 0),
                'amount_paid': payment_info.get('amount_received', 0),
                'change_given': payment_info.get('change', 0),
                'status': 'paid'  # Mark as paid, will update to 'completed' after printing
            }
            
            # Log to database using PaymentModel's db_manager
            self.db_manager.log_transaction(transaction_data)
            print(f"Transaction logged immediately: {transaction_data['file_name']}")
                
        except Exception as e:
            print(f"Error logging transaction immediately: {e}")

    def update_coin_inventory_after_payment(self, coin_data=None, add=True):
        try:
            if coin_data is None:
                coin_data = self.cash_received
            
            # Add received coins to inventory
            if not coin_data:
                return
            
            # Get current inventory once 
            current_inventory = self.db_manager.get_cash_inventory()
            
            for denomination, count in coin_data.items():
                if count > 0:
                    is_bill = denomination >= 20
                    
                    # Only process coins 1 and 5 peso when dispensing change
                    if not add and denomination not in [1, 5]:
                        continue
                    
                    # Find current count from inventory
                    current_count = 0
                    for item in current_inventory:
                        if (item.get('denomination') == denomination and 
                            item.get('type') == ('bill' if is_bill else 'coin')):
                            current_count = item.get('count', 0)
                            break
                    
                    # Calculate new count
                    if add:
                        new_count = current_count + count
                    else:
                        new_count = max(0, current_count - count)  # Don't go below 0
                    
                    # Update database
                    self.db_manager.update_cash_inventory(
                        denomination=denomination,
                        count=new_count,
                        type='bill' if is_bill else 'coin'
                    )
                    
                    operation_symbol = "+" if add else "-"
                    print(f"Updated {denomination} {'bill' if is_bill else 'coin'}: {current_count} {operation_symbol}{count} = {new_count}")
            
            print("Coin inventory updated")
                    
        except Exception as e:
            print(f"Error updating coin inventory: {e}")

    # Completed payment, logging, and dispensing change
    def complete_payment(self): # Returns true if success
        try:
            # Validate payment data exists
            if self.payment_data is None:
                return False, "No payment data available"

            # Calculate change to dispense
            change_amount = self.amount_received - self.total_cost
            print(f"Payment calculation - received: {self.amount_received}, cost: {self.total_cost}, change: {change_amount}")

            # Create transaction data and log immediately so it exists regardless of print outcome
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
            print(f"Transaction data created")
            self.db_manager.log_transaction(self.transaction_data)

            # Stop any existing dispense thread to prevent conflicts
            if self.dispense_thread and self.dispense_thread.isRunning():
                self.dispense_thread.terminate()
                self.dispense_thread.wait(1000)
                self.dispense_thread = None

            # Create change dispenser if it was cleaned up (ex: after leaving payment screen)
            if self.change_dispenser is None:
                from managers.hopper_manager import ChangeDispenser
                self.change_dispenser = ChangeDispenser()

            # Start dispensing change in a separate thread
            if change_amount > 0:
                print(f"Starting change dispensing for P{change_amount:.2f}")
                # Compute required coins using payment algorithm 
                can_dispense, reason, required_coins = self.payment_algorithm.can_dispense_change(change_amount)
                if not can_dispense:
                    print(f"Change not dispensable: {reason}. Not giving u back ur money.")
                    required_coins = None

                self.dispense_thread = DispenseThread(
                    dispenser=self.change_dispenser,
                    amount=change_amount,
                    required_coins=required_coins
                )
                self.dispense_thread.status_update.connect(self.payment_status_updated.emit)
                self.dispense_thread.dispensing_finished.connect(self._on_dispensing_finished)
                self.dispense_thread.start()
                print("Dispense thread started")
            else:
                print("No change to dispense, proceeding to printing")
                self._start_printing()

            return True, "Payment processing started"

        except Exception as e:
            print(f"ERROR: Error in payment completion: {e}")
            # Reset payment completing flag on error
            self._payment_completing = False
            return False, f"Payment completion failed: {str(e)}"

    def _on_dispensing_finished(self, result):
        try:
            if isinstance(result, dict) and result.get('success', False):
                # New flow: Update database with actual coins dispensed, then print
                coins_1 = result.get('coins_1', 0)
                coins_5 = result.get('coins_5', 0)
                actual_change = result.get('actual_change', 0)
                expected_change = result.get('expected_change', 0)

                print(f"Change dispensing completed - P1={coins_1}, P5={coins_5}, actual={actual_change}, expected={expected_change}")
                self.payment_status_updated.emit(f"Change dispensed! Updating inventory...")

                # Store dispensed change data for later database update
                self.change_dispensed = {1: coins_1, 5: coins_5}

                # Update database immediately when coins are dispensed
                if coins_1 > 0 or coins_5 > 0:
                    print(f"Updating database with dispensed coins: P1={coins_1}, P5={coins_5}")
                    coin_data = {1: coins_1, 5: coins_5}
                    self.update_coin_inventory_after_payment(coin_data=coin_data, add=False)
                    # Prevent double subtraction later in the post-print step
                    self.change_dispensed = None

                self._start_printing()
            else:
                print("Error dispensing change.")
                self._navigate_to_thank_you()
        except Exception as e:
            print(f"Exception in _on_dispensing_finished: {e}")
            # Fallback to navigation even if there's an error
            self._navigate_to_thank_you()

        # Clean up change dispenser after dispensing is complete
        try:
            if self.change_dispenser:
                print("Cleaning up change dispenser after dispensing complete")
                self.change_dispenser.cleanup()
                # Don't set to None here as it might be needed for future transactions
        except Exception as e:
            print(f"Error cleaning up change dispenser: {e}")

        # Clean up the dispense thread
        try:
            if self.dispense_thread:
                print("Cleaning up dispense thread after completion")
                if self.dispense_thread.isRunning():
                    self.dispense_thread.terminate()
                    self.dispense_thread.wait(1000)
                self.dispense_thread = None
        except Exception as e:
            print(f"Error cleaning up dispense thread: {e}")

    def _start_printing(self):
        try:
            # Defensive write so that printer targets the same metadata
            print_job_details = {
                'file_path': self.payment_data['pdf_data']['path'],
                'selected_pages': self.payment_data.get('selected_pages', [1]),
                'copies': self.payment_data.get('copies', 1),
                'color_mode': self.payment_data.get('color_mode', 'Color')
            }
            self.main_app.current_print_job = print_job_details

            self._navigate_to_thank_you()

        except Exception as e:
            print(f"Error starting printing: {e}")
            self.payment_status_updated.emit(f"Printing error: {str(e)}")
            # Try to navigate to thank you screen anyway
            try:
                self._navigate_to_thank_you()
            except Exception as nav_error:
                print(f"Error navigating to thank you screen: {nav_error}")


    def _navigate_to_thank_you(self):
        # Create payment_info with all necessary data including cash_received data also passed to main
        if self.payment_data:
            self.payment_info = {
                'pdf_data': self.payment_data.get('pdf_data', {}),
                'selected_pages': self.payment_data.get('selected_pages', []),
                'copies': self.payment_data.get('copies', 1),
                'color_mode': self.payment_data.get('color_mode', 'Color'),
                'total_cost': self.total_cost,
                'amount_received': self.amount_received,
                'cash_received': self.cash_received.copy(),  # Include coin data for database update
                'change_dispensed': getattr(self, 'change_dispensed', None)
            }
            self.log_transaction(self.payment_info)
            self.update_coin_inventory_after_payment()
            print(f"Database updated")
            self.payment_completed.emit(self.payment_info) # Run printing in main
        else:
            print("No payment data available to create payment info")


    def reset_payment_state(self):
        # Reset payment completing flag
        self._payment_completing = False

        # Reset payment amounts
        self.amount_received = 0
        self.total_cost = 0
        self.cash_received = {}

        # Reset payment data
        self.payment_data = None

        # Stop any running dispense thread
        if hasattr(self, 'dispense_thread') and self.dispense_thread and self.dispense_thread.isRunning():
            print("Stopping dispense thread during reset")
            self.dispense_thread.terminate()
            self.dispense_thread.wait(1000)
            self.dispense_thread = None

        # Reset payment ready state
        self.payment_ready = False

        # Emit reset signals
        self.amount_received_updated.emit(0)
        self.change_updated.emit(0, "")
        self.payment_status_updated.emit("Payment screen ready")

        print("Payment state reset")


    def go_back(self):
        # Update inventory with received money (no refunds, so money stays in machine)
        if self.amount_received > 0 and self.cash_received:
            print(f"Adding received money to inventory - {self.cash_received}")
            try:
                current_inventory = {}
                for item in (self.db_manager.get_cash_inventory() or []):
                    if item.get('type') == 'coin' or item.get('type') == 'bill':
                        current_inventory[(item.get('type'), int(item.get('denomination')))] = int(item.get('count') or 0)

                for denomination, count in self.cash_received.items():
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
                print(f"Failed to update cash inventory on cancel: {inv_err}")

        self.on_leave()
        self.reset_payment_state()
        self.go_back_requested.emit()

    def on_enter(self):
        self.setup_gpio()
        # Reset payment state
        self.amount_received = 0
        self.cash_received = {}
        self._payment_completing = False  # Reset payment completion flag

        self.amount_received_updated.emit(0)
        self.change_updated.emit(0, "")

        # If data ready, enable payment mode
        if self.total_cost > 0:
            self.enable_payment_mode()
        else:
            print("No payment data yet.")

    def on_leave(self):
        # Disable payment mode and coin acceptor
        self.disable_payment_mode()

        # Stop and cleanup payment handler
        if self.payment_handler:
            self.payment_handler.cleanup()
            self.payment_handler = None
        
        # Clean up global payment handler to in case
        cleanup_payment_handler()

        # Stop any running dispense thread in case
        if self.dispense_thread:
            try:
                if self.dispense_thread.isRunning():
                    self.dispense_thread.terminate()
                    self.dispense_thread.wait(1000)
            except Exception as e:
                print(f"Error stopping dispense thread: {e}")
            finally:
                # Clear the thread reference
                self.dispense_thread = None

        # Clean up change dispenser (thread is already stopped above)
        if self.change_dispenser:
            try:
                self.change_dispenser.cleanup()
            except Exception as e:
                print(f"Error cleaning up change dispenser: {e}")
            finally:
                self.change_dispenser = None