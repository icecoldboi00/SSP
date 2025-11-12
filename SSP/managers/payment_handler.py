import time
import threading
from typing import Dict
from PyQt5.QtCore import QObject, pyqtSignal

# Check for pigpio availability
try:
    import pigpio
    PIGPIO_AVAILABLE = True
    print("SUCCESS: pigpio library found. Payment handler is ENABLED.")
except ImportError:
    PIGPIO_AVAILABLE = False
    print("WARNING: pigpio library not found. Payment handler will be SIMULATED.")


class PaymentHandler(QObject):
    coin_inserted = pyqtSignal(int)  # coin_value
    special_coin_inserted = pyqtSignal(int)  # special coin_value (cannot be given as change)
    bill_inserted = pyqtSignal(int)  # bill_value
    payment_status = pyqtSignal(str)  # status_message
    acceptor_state_changed = pyqtSignal(bool)  # enabled/disabled
    
    def __init__(self):
        super().__init__()
        self.pi = None
        self.gpio_available = PIGPIO_AVAILABLE
        
        # Pin configuration (exact from coinbill.py + GPIO 22 for coin inhibit)
        self.COIN_PIN = 20          # Coin pulse input pin
        self.BILL_PIN = 18         # Bill pulse input pin
        self.COIN_INHIBIT_PIN = 22 # Coin acceptor disable pin (active low)
        self.BILL_INHIBIT_PIN = 23 # Bill acceptor disable pin (active high)
        
        # Pulse counting variables (exact from coinbill.py)
        self.coin_pulse_count = 0
        self.coin_last_pulse_time = time.time()
        
        self.bill_pulse_count = 0
        self.bill_last_pulse_time = time.time()
        
        # Timing constants (exact from coinbill.py)
        self.COIN_TIMEOUT = 0.3     # Time to wait for coin completion
        self.PULSE_TIMEOUT = 0.5    # Time to wait for bill completion
        self.DEBOUNCE_TIME = 0.1    # Minimum time between pulses
        
        # Payment state
        self.coin_enabled = False
        self.bill_enabled = False
        self.accepting_payments = False
        
        # Callbacks
        self.coin_callback = None
        self.bill_callback = None
        
        # Processing thread
        self.processing_thread = None
        self.stop_processing = False
    
    def initialize(self) -> bool:
        if not self.gpio_available:
            print("PaymentHandler: GPIO not available - running in simulation mode")
            return False
        
        try:
            # Initialize pigpio (exact from coinbill.py)
            self.pi = pigpio.pi()
            if not self.pi.connected:
                print("Failed to connect to pigpio daemon")
                return False
            
            print("Successfully connected to pigpio daemon")
            
            # Setup GPIO pins (exact from coinbill.py + coin inhibit)
            self._setup_gpio_pins()
            
            # Set initial state (disabled)
            self.disable_all_acceptors()
            
            # Start processing thread
            self._start_processing_thread()
            
            print("Payment system initialization complete")
            return True
            
        except Exception as e:
            print(f"Initialization failed - {e}")
            return False
    
    def _setup_gpio_pins(self):
        try:
            # Coin acceptor setup (exact from coinbill.py)
            self.pi.set_mode(self.COIN_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.COIN_PIN, pigpio.PUD_UP)
            self.coin_callback = self.pi.callback(self.COIN_PIN, pigpio.FALLING_EDGE, self._coin_pulse_detected)
            
            # Bill acceptor setup (exact from coinbill.py)
            self.pi.set_mode(self.BILL_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.BILL_PIN, pigpio.PUD_UP)
            self.pi.set_mode(self.BILL_INHIBIT_PIN, pigpio.OUTPUT)
            
            # Coin acceptor inhibit pin (new addition)
            self.pi.set_mode(self.COIN_INHIBIT_PIN, pigpio.OUTPUT)
            
            self.bill_callback = self.pi.callback(self.BILL_PIN, pigpio.FALLING_EDGE, self._bill_pulse_detected)
            
            print(f"GPIO pins configured - Coin: {self.COIN_PIN}, Bill: {self.BILL_PIN}")
            print(f"Inhibit pins - Coin: {self.COIN_INHIBIT_PIN}, Bill: {self.BILL_INHIBIT_PIN}")
            
        except Exception as e:
            print(f"GPIO setup failed - {e}")
            raise
    
    def _coin_pulse_detected(self, gpio, level, tick):
        if gpio != self.COIN_PIN:
            return
        
        if not self.accepting_payments:
            return
        
        current_time = time.time()
        if current_time - self.coin_last_pulse_time > self.DEBOUNCE_TIME:
            self.coin_pulse_count += 1
            self.coin_last_pulse_time = current_time
            print(f"Coin pulse detected - Count: {self.coin_pulse_count}")
    
    def _bill_pulse_detected(self, gpio, level, tick):
        if gpio != self.BILL_PIN:
            return
        
        if not self.accepting_payments:
            return
        
        current_time = time.time()
        if current_time - self.bill_last_pulse_time > self.DEBOUNCE_TIME:
            self.bill_pulse_count += 1
            self.bill_last_pulse_time = current_time
            print(f"Bill pulse detected - Count: {self.bill_pulse_count}")
    
    def _start_processing_thread(self):
        self.stop_processing = False
        self.processing_thread = threading.Thread(target=self._processing_loop, daemon=True)
        self.processing_thread.start()
        print("Processing thread started")
    
    def _processing_loop(self):
        while not self.stop_processing:
            try:
                now = time.time()
                
                # Process coin pulses (exact from coinbill.py)
                if self.coin_pulse_count > 0 and (now - self.coin_last_pulse_time > self.COIN_TIMEOUT):
                    print(f"Processing coin with {self.coin_pulse_count} pulses")
                    value, is_special = self._get_coin_value(self.coin_pulse_count)
                    if value > 0:
                        if is_special:
                            print(f"Processing special coin - {value} peso (cannot be given as change)")
                            self.special_coin_inserted.emit(value)
                        else:
                            print(f"Processing regular coin - {value} peso")
                            self.coin_inserted.emit(value)
                    else:
                        print(f"Coin with {self.coin_pulse_count} pulses not recognized as valid coin")
                    self.coin_pulse_count = 0
                
                # Process bill pulses (exact from coinbill.py)
                if self.bill_pulse_count > 0 and (now - self.bill_last_pulse_time > self.PULSE_TIMEOUT):
                    print(f"Processing bill with {self.bill_pulse_count} pulses")
                    value = self._get_bill_value(self.bill_pulse_count)
                    if value > 0:
                        print(f"Processing bill - {value} peso")
                        self.bill_inserted.emit(value)
                    else:
                        print(f"Bill with {self.bill_pulse_count} pulses not recognized as valid bill")
                    self.bill_pulse_count = 0
                
                time.sleep(0.05)  # Exact from coinbill.py
                
            except Exception as e:
                print(f"Error in processing loop - {e}")
                time.sleep(0.1)
    
    def _get_coin_value(self, pulses: int) -> tuple:
        print(f"Processing {pulses} pulses for coin value")
        
        # Exact implementation from coinbill.py
        if 3 <= pulses <= 4:
            return (1, False)  # (value, is_special)
        elif 5 <= pulses <= 6:
            return (5, False)  # (value, is_special)
        elif 8 <= pulses <= 9:
            return (10, False)  # (value, is_special)
        elif 11 <= pulses <= 12:
            return (20, False)  # (value, is_special)
        elif 14 <= pulses <= 15:
            return (5, True)  # (value, is_special) - special 5 peso that cannot be given as change
        else:
            print(f"Unknown coin pulse count: {pulses}")
            return (0, False)  # (value, is_special)
    
    def _get_bill_value(self, pulses: int) -> int:
        if pulses == 2:
            return 20  # ₱20 bill
        elif pulses == 5:
            return 50  # ₱50 bill
        elif pulses == 10:
            return 100  # ₱100 bill
        elif pulses == 50:
            return 500  # ₱500 bill
        else:
            print(f"Unknown bill pulse count: {pulses}")
            return 0
    
    def enable_payments(self):
        if not self.gpio_available or not self.pi:
            print("Cannot enable payments - GPIO not available")
            return False
        
        try:
            # Reset pulse counts
            self.coin_pulse_count = 0
            self.bill_pulse_count = 0
            
            # Enable coin acceptor (HIGH = enabled, LOW = disabled - active low)
            self.pi.write(self.COIN_INHIBIT_PIN, 1)
            self.coin_enabled = True
            
            # Enable bill acceptor (LOW = enabled, HIGH = disabled)
            self.pi.write(self.BILL_INHIBIT_PIN, 0)
            self.bill_enabled = True
            
            self.accepting_payments = True
            
            print("Payment acceptors enabled")
            self.payment_status.emit("Payment acceptors enabled - Insert coins or bills")
            self.acceptor_state_changed.emit(True)
            
            return True
            
        except Exception as e:
            print(f"Failed to enable payments - {e}")
            return False
    
    def disable_payments(self):
        if not self.gpio_available or not self.pi:
            print("Cannot disable payments - GPIO not available")
            return False
        
        try:
            # Disable coin acceptor (LOW = disabled - active low)
            self.pi.write(self.COIN_INHIBIT_PIN, 0)
            self.coin_enabled = False
            
            # Disable bill acceptor (HIGH = disabled)
            self.pi.write(self.BILL_INHIBIT_PIN, 1)
            self.bill_enabled = False
            
            self.accepting_payments = False
            
            print("Payment acceptors disabled")
            self.payment_status.emit("Payment acceptors disabled")
            self.acceptor_state_changed.emit(False)
            
            return True
            
        except Exception as e:
            print(f"Failed to disable payments - {e}")
            return False
    
    def disable_all_acceptors(self):
        if self.gpio_available and self.pi:
            try:
                self.pi.write(self.COIN_INHIBIT_PIN, 0)  # Disable coin acceptor (active low)
                self.pi.write(self.BILL_INHIBIT_PIN, 1)  # Disable bill acceptor
                self.coin_enabled = False
                self.bill_enabled = False
                self.accepting_payments = False
                print("All acceptors disabled")
            except Exception as e:
                print(f"Error disabling acceptors - {e}")
    
    def get_status(self) -> Dict:
        return {
            'gpio_available': self.gpio_available,
            'connected': self.pi.connected if self.pi else False,
            'coin_enabled': self.coin_enabled,
            'bill_enabled': self.bill_enabled,
            'accepting_payments': self.accepting_payments,
            'processing_thread_active': self.processing_thread and self.processing_thread.is_alive()
        }
    
    def test_coin_detection(self, value: int = 1):
        if self.accepting_payments:
            print(f"Testing coin detection - {value} peso")
            self.coin_inserted.emit(value)
        else:
            print("Cannot test - payments not enabled")
    
    def test_bill_detection(self, value: int = 20):
        if self.accepting_payments:
            print(f"Testing bill detection - {value} peso")
            self.bill_inserted.emit(value)
        else:
            print("Cannot test - payments not enabled")
    
    def cleanup(self):
        try:
            print("Starting cleanup")
            # Stop processing thread
            self.stop_processing = True
            if hasattr(self, 'processing_thread') and self.processing_thread and getattr(self.processing_thread, 'is_alive', lambda : False)():
                self.processing_thread.join(timeout=1.0)
            # Disable all acceptors first
            if self.gpio_available and getattr(self, 'pi', None):
                try:
                    self.disable_all_acceptors()
                except Exception as e:
                    print(f"Error disabling acceptors - {e}")
                # Clean up callbacks
                if getattr(self, 'coin_callback', None):
                    try:
                        self.coin_callback.cancel()
                    except Exception as e:
                        print(f"Error canceling coin callback - {e}")
                    finally:
                        self.coin_callback = None
                if getattr(self, 'bill_callback', None):
                    try:
                        self.bill_callback.cancel()
                    except Exception as e:
                        print(f"Error canceling bill callback - {e}")
                    finally:
                        self.bill_callback = None
                # Close pigpio connection
                try:
                    if hasattr(self.pi, 'connected') and self.pi.connected:
                        self.pi.stop()
                except Exception as e:
                    print(f"Error stopping pigpio - {e}")
                finally:
                    self.pi = None
            # Reset all state
            self.coin_enabled = False
            self.bill_enabled = False
            self.accepting_payments = False
            self.coin_pulse_count = 0
            self.bill_pulse_count = 0
            print("Cleanup complete")
        except Exception as e:
            print(f"Cleanup error - {e}")
        finally:
            # Ensure we're in a clean state
            self.gpio_available = False
    
    def __del__(self):
        self.cleanup()


# Global payment handler instance
_payment_handler_instance = None

def get_payment_handler() -> PaymentHandler:
    global _payment_handler_instance
    
    # Always create a fresh instance to ensure we have the latest code
    if _payment_handler_instance is not None:
        print("Cleaning up existing instance before creating new one")
        try:
            _payment_handler_instance.cleanup()
        except Exception as e:
            print(f"Error during cleanup - {e}")
        finally:
            _payment_handler_instance = None
    
    # Create new instance
    _payment_handler_instance = PaymentHandler()
    if not _payment_handler_instance.initialize():
        print("Initialization failed, cleaning up")
        _payment_handler_instance.cleanup()
        _payment_handler_instance = None
        return None
    
    return _payment_handler_instance

def cleanup_payment_handler():
    global _payment_handler_instance
    if _payment_handler_instance:
        try:
            _payment_handler_instance.cleanup()
        except Exception as e:
            print(f"Error during cleanup - {e}")
        finally:
            _payment_handler_instance = None