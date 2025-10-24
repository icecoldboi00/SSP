# managers/payment_handler.py

import time
import threading
from typing import Dict, Optional, Callable
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

# Check for pigpio availability
try:
    import pigpio
    PIGPIO_AVAILABLE = True
    print("SUCCESS: pigpio library found. Payment handler is ENABLED.")
except ImportError:
    PIGPIO_AVAILABLE = False
    print("WARNING: pigpio library not found. Payment handler will be SIMULATED.")


class PaymentHandler(QObject):
    """
    Dedicated payment handler for coin and bill acceptors.
    Handles GPIO operations, pulse detection, and payment processing.
    """
    
    # Signals for payment events
    coin_inserted = pyqtSignal(int)  # coin_value
    bill_inserted = pyqtSignal(int)  # bill_value
    payment_status = pyqtSignal(str)  # status_message
    acceptor_state_changed = pyqtSignal(bool)  # enabled/disabled
    
    def __init__(self):
        super().__init__()
        self.pi = None
        self.gpio_available = PIGPIO_AVAILABLE
        
        # GPIO Pin Configuration
        self.COIN_PIN = 5          # Coin acceptor signal pin
        self.BILL_PIN = 18         # Bill acceptor signal pin
        self.COIN_INHIBIT_PIN = 22 # Coin acceptor control pin
        self.BILL_INHIBIT_PIN = 23 # Bill acceptor control pin
        
        # Payment state
        self.coin_enabled = False
        self.bill_enabled = False
        self.accepting_payments = False
        
        # Pulse detection
        self.coin_pulse_count = 0
        self.bill_pulse_count = 0
        self.coin_last_pulse_time = 0
        self.bill_last_pulse_time = 0
        
        # Timing constants
        self.DEBOUNCE_TIME = 0.2      # Minimum time between pulses
        self.COIN_TIMEOUT = 0.5       # Time to wait for coin completion
        self.BILL_TIMEOUT = 1.0       # Time to wait for bill completion
        
        # Cooldown management
        self.coin_cooldown_active = False
        self.coin_cooldown_duration = 0.5  # 500ms cooldown after coin detection
        
        # Callbacks
        self.coin_callback = None
        self.bill_callback = None
        
        print("PaymentHandler initialized")
    
    def initialize(self) -> bool:
        """Initialize GPIO connection and setup."""
        if not self.gpio_available:
            print("PaymentHandler: GPIO not available - running in simulation mode")
            return False
        
        try:
            # Create pigpio connection
            self.pi = pigpio.pi()
            if not self.pi.connected:
                print("PaymentHandler: Failed to connect to pigpio daemon")
                return False
            
            print("PaymentHandler: Successfully connected to pigpio daemon")
            
            # Setup GPIO pins
            self._setup_gpio_pins()
            
            # Set initial state (disabled)
            self.disable_all_acceptors()
            
            print("PaymentHandler: Initialization complete")
            return True
            
        except Exception as e:
            print(f"PaymentHandler: Initialization failed - {e}")
            return False
    
    def _setup_gpio_pins(self):
        """Setup GPIO pins for coin and bill acceptors."""
        try:
            # Setup coin acceptor
            self.pi.set_mode(self.COIN_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.COIN_PIN, pigpio.PUD_UP)
            self.coin_callback = self.pi.callback(self.COIN_PIN, pigpio.FALLING_EDGE, self._coin_pulse_detected)
            
            # Setup bill acceptor
            self.pi.set_mode(self.BILL_PIN, pigpio.INPUT)
            self.pi.set_pull_up_down(self.BILL_PIN, pigpio.PUD_UP)
            self.bill_callback = self.pi.callback(self.BILL_PIN, pigpio.FALLING_EDGE, self._bill_pulse_detected)
            
            # Setup control pins
            self.pi.set_mode(self.COIN_INHIBIT_PIN, pigpio.OUTPUT)
            self.pi.set_mode(self.BILL_INHIBIT_PIN, pigpio.OUTPUT)
            
            print(f"PaymentHandler: GPIO pins configured - Coin: {self.COIN_PIN}, Bill: {self.BILL_PIN}")
            
        except Exception as e:
            print(f"PaymentHandler: GPIO setup failed - {e}")
            raise
    
    def _coin_pulse_detected(self, gpio, level, tick):
        """Handle coin pulse detection."""
        if not self.accepting_payments or self.coin_cooldown_active:
            return
        
        current_time = time.time()
        
        # Debounce check
        if current_time - self.coin_last_pulse_time < self.DEBOUNCE_TIME:
            return
        
        self.coin_pulse_count += 1
        self.coin_last_pulse_time = current_time
        
        print(f"PaymentHandler: Coin pulse detected - GPIO: {gpio}, Count: {self.coin_pulse_count}")
        
        # Process coin immediately
        self._process_coin_detection()
    
    def _bill_pulse_detected(self, gpio, level, tick):
        """Handle bill pulse detection."""
        if not self.accepting_payments:
            return
        
        current_time = time.time()
        
        # Debounce check
        if current_time - self.bill_last_pulse_time < self.DEBOUNCE_TIME:
            return
        
        self.bill_pulse_count += 1
        self.bill_last_pulse_time = current_time
        
        print(f"PaymentHandler: Bill pulse detected - GPIO: {gpio}, Count: {self.bill_pulse_count}")
        
        # Process bill detection
        self._process_bill_detection()
    
    def _process_coin_detection(self):
        """Process detected coin and emit signal."""
        if self.coin_pulse_count >= 1:
            value = self._get_coin_value(self.coin_pulse_count)
            if value > 0:
                print(f"PaymentHandler: Processing coin - {value} peso")
                self.coin_inserted.emit(value)
                
                # Start cooldown to prevent double detection
                self._start_coin_cooldown()
            
            # Reset pulse count
            self.coin_pulse_count = 0
    
    def _process_bill_detection(self):
        """Process detected bill and emit signal."""
        if self.bill_pulse_count >= 1:
            value = self._get_bill_value(self.bill_pulse_count)
            if value > 0:
                print(f"PaymentHandler: Processing bill - {value} peso")
                self.bill_inserted.emit(value)
            
            # Reset pulse count
            self.bill_pulse_count = 0
    
    def _get_coin_value(self, pulses: int) -> int:
        """Convert pulse count to coin value."""
        if pulses == 1:
            return 1  # ₱1 coin
        elif pulses == 5:
            return 5  # ₱5 coin
        elif pulses == 10:
            return 10  # ₱10 coin
        elif pulses == 20:
            return 20  # ₱20 coin
        elif 4 <= pulses <= 6:
            return 5  # ₱5 coin with variation
        elif 9 <= pulses <= 11:
            return 10  # ₱10 coin with variation
        elif 18 <= pulses <= 22:
            return 20  # ₱20 coin with variation
        else:
            print(f"PaymentHandler: Unknown coin pulse count: {pulses}")
            return 0
    
    def _get_bill_value(self, pulses: int) -> int:
        """Convert pulse count to bill value."""
        if pulses == 2:
            return 20  # ₱20 bill
        elif pulses == 5:
            return 50  # ₱50 bill
        elif pulses == 10:
            return 100  # ₱100 bill
        elif pulses == 50:
            return 500  # ₱500 bill
        else:
            print(f"PaymentHandler: Unknown bill pulse count: {pulses}")
            return 0
    
    def _start_coin_cooldown(self):
        """Start cooldown period to prevent double coin detection."""
        self.coin_cooldown_active = True
        print("PaymentHandler: Starting coin cooldown")
        
        def end_cooldown():
            time.sleep(self.coin_cooldown_duration)
            self.coin_cooldown_active = False
            print("PaymentHandler: Coin cooldown ended")
        
        threading.Thread(target=end_cooldown, daemon=True).start()
    
    def enable_payments(self):
        """Enable both coin and bill acceptors."""
        if not self.gpio_available or not self.pi:
            print("PaymentHandler: Cannot enable payments - GPIO not available")
            return False
        
        try:
            # Enable coin acceptor (HIGH = enabled)
            self.pi.write(self.COIN_INHIBIT_PIN, 1)
            self.coin_enabled = True
            
            # Enable bill acceptor (LOW = enabled)
            self.pi.write(self.BILL_INHIBIT_PIN, 0)
            self.bill_enabled = True
            
            self.accepting_payments = True
            
            print("PaymentHandler: Payment acceptors enabled")
            self.payment_status.emit("Payment acceptors enabled - Insert coins or bills")
            self.acceptor_state_changed.emit(True)
            
            return True
            
        except Exception as e:
            print(f"PaymentHandler: Failed to enable payments - {e}")
            return False
    
    def disable_payments(self):
        """Disable both coin and bill acceptors."""
        if not self.gpio_available or not self.pi:
            print("PaymentHandler: Cannot disable payments - GPIO not available")
            return False
        
        try:
            # Disable coin acceptor (LOW = disabled)
            self.pi.write(self.COIN_INHIBIT_PIN, 0)
            self.coin_enabled = False
            
            # Disable bill acceptor (HIGH = disabled)
            self.pi.write(self.BILL_INHIBIT_PIN, 1)
            self.bill_enabled = False
            
            self.accepting_payments = False
            
            print("PaymentHandler: Payment acceptors disabled")
            self.payment_status.emit("Payment acceptors disabled")
            self.acceptor_state_changed.emit(False)
            
            return True
            
        except Exception as e:
            print(f"PaymentHandler: Failed to disable payments - {e}")
            return False
    
    def disable_all_acceptors(self):
        """Disable all acceptors (startup state)."""
        if self.gpio_available and self.pi:
            try:
                self.pi.write(self.COIN_INHIBIT_PIN, 0)  # Disable coin acceptor
                self.pi.write(self.BILL_INHIBIT_PIN, 1)  # Disable bill acceptor
                self.coin_enabled = False
                self.bill_enabled = False
                self.accepting_payments = False
                print("PaymentHandler: All acceptors disabled")
            except Exception as e:
                print(f"PaymentHandler: Error disabling acceptors - {e}")
    
    def get_status(self) -> Dict:
        """Get current payment handler status."""
        return {
            'gpio_available': self.gpio_available,
            'connected': self.pi.connected if self.pi else False,
            'coin_enabled': self.coin_enabled,
            'bill_enabled': self.bill_enabled,
            'accepting_payments': self.accepting_payments,
            'coin_cooldown_active': self.coin_cooldown_active
        }
    
    def test_coin_detection(self, value: int = 1):
        """Test coin detection by simulating a coin insertion."""
        if self.accepting_payments:
            print(f"PaymentHandler: Testing coin detection - {value} peso")
            self.coin_inserted.emit(value)
        else:
            print("PaymentHandler: Cannot test - payments not enabled")
    
    def test_bill_detection(self, value: int = 20):
        """Test bill detection by simulating a bill insertion."""
        if self.accepting_payments:
            print(f"PaymentHandler: Testing bill detection - {value} peso")
            self.bill_inserted.emit(value)
        else:
            print("PaymentHandler: Cannot test - payments not enabled")
    
    def cleanup(self):
        """Clean up GPIO resources."""
        try:
            if self.gpio_available and self.pi:
                # Disable all acceptors
                self.disable_all_acceptors()
                
                # Clean up callbacks
                if self.coin_callback:
                    self.coin_callback.cancel()
                    self.coin_callback = None
                
                if self.bill_callback:
                    self.bill_callback.cancel()
                    self.bill_callback = None
                
                # Close pigpio connection
                self.pi.stop()
                self.pi = None
                
                print("PaymentHandler: Cleanup complete")
                
        except Exception as e:
            print(f"PaymentHandler: Cleanup error - {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup."""
        self.cleanup()


# Global payment handler instance
_payment_handler_instance = None

def get_payment_handler() -> PaymentHandler:
    """Get the global payment handler instance."""
    global _payment_handler_instance
    if _payment_handler_instance is None:
        _payment_handler_instance = PaymentHandler()
        _payment_handler_instance.initialize()
    return _payment_handler_instance

def cleanup_payment_handler():
    """Clean up the global payment handler instance."""
    global _payment_handler_instance
    if _payment_handler_instance:
        _payment_handler_instance.cleanup()
        _payment_handler_instance = None
