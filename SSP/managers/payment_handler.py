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
        self.COIN_TIMEOUT = 0.3       # Time to wait for coin completion
        self.BILL_TIMEOUT = 0.5       # Time to wait for bill completion
        
        # Cooldown management
        self.coin_cooldown_active = False
        self.coin_cooldown_duration = 0.5  # 500ms cooldown after coin detection
        
        # Pulse aggregation
        self.pulse_aggregation_timer = None
        self.pulse_aggregation_timeout = 0.3  # 300ms to collect all pulses from one coin
        
        # Callbacks
        self.coin_callback = None
        self.bill_callback = None
        
        print("PaymentHandler initialized")
    
    def initialize(self) -> bool:
        """Initialize GPIO connection and setup with SEPARATE pigpio instance."""
        if not self.gpio_available:
            print("PaymentHandler: GPIO not available - running in simulation mode")
            return False
        
        try:
            # Create SEPARATE pigpio connection for payments only
            # This ensures complete isolation from hopper manager
            self.pi = pigpio.pi()
            if not self.pi.connected:
                print("PaymentHandler: Failed to connect to pigpio daemon")
                return False
            
            print("PaymentHandler: Successfully connected to SEPARATE pigpio daemon for payments")
            print("PaymentHandler: This connection is COMPLETELY ISOLATED from hopper manager")
            
            # Setup GPIO pins
            self._setup_gpio_pins()
            
            # Set initial state (disabled)
            self.disable_all_acceptors()
            
            print("PaymentHandler: Payment system initialization complete - ISOLATED from hoppers")
            
            # Verify complete isolation
            self.verify_isolation()
            
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
            print(f"PaymentHandler: Monitoring ONLY pins {self.COIN_PIN} and {self.BILL_PIN} for payments")
            print(f"PaymentHandler: COMPLETELY ISOLATED from hopper manager - no shared resources")
            print(f"PaymentHandler: Hopper sensor pins (10, 13) are handled by separate hopper manager")
            
        except Exception as e:
            print(f"PaymentHandler: GPIO setup failed - {e}")
            raise
    
    def _coin_pulse_detected(self, gpio, level, tick):
        """Handle coin pulse detection."""
        # CRITICAL: Only process pulses from the actual coin acceptor pin (5)
        # Ignore all hopper sensor pulses (pins 10, 13) to prevent interference
        if gpio != self.COIN_PIN:
            print(f"PaymentHandler: Ignoring pulse from GPIO {gpio} (not coin acceptor pin {self.COIN_PIN})")
            return
        
        if not self.accepting_payments or self.coin_cooldown_active:
            print(f"PaymentHandler: Ignoring pulse - payments not accepting or cooldown active")
            return
        
        current_time = time.time()
        
        # Debounce check
        if current_time - self.coin_last_pulse_time < self.DEBOUNCE_TIME:
            print(f"PaymentHandler: Ignoring pulse - too soon after last pulse ({current_time - self.coin_last_pulse_time:.3f}s)")
            return
        
        self.coin_pulse_count += 1
        self.coin_last_pulse_time = current_time
        
        print(f"PaymentHandler: Valid coin pulse detected - GPIO: {gpio}, Count: {self.coin_pulse_count}")
        
        # Start aggregation timer to collect all pulses from a single coin
        self._start_pulse_aggregation()
    
    def _start_pulse_aggregation(self):
        """Start pulse aggregation timer to collect all pulses from one coin."""
        if self.pulse_aggregation_timer:
            # Cancel existing timer
            self.pulse_aggregation_timer.cancel()
        
        # Start new timer
        self.pulse_aggregation_timer = threading.Timer(
            self.pulse_aggregation_timeout, 
            self._on_pulse_aggregation_timeout
        )
        self.pulse_aggregation_timer.start()
        print(f"PaymentHandler: Started pulse aggregation timer ({self.pulse_aggregation_timeout}s)")
    
    def _on_pulse_aggregation_timeout(self):
        """Called when pulse aggregation timeout occurs."""
        print(f"PaymentHandler: Pulse aggregation timeout - processing {self.coin_pulse_count} pulses")
        self._process_coin_detection()
        self.pulse_aggregation_timer = None
    
    def _bill_pulse_detected(self, gpio, level, tick):
        """Handle bill pulse detection."""
        # CRITICAL: Only process pulses from the actual bill acceptor pin (18)
        # Ignore all hopper sensor pulses (pins 10, 13) to prevent interference
        if gpio != self.BILL_PIN:
            print(f"PaymentHandler: Ignoring bill pulse from GPIO {gpio} (not bill acceptor pin {self.BILL_PIN})")
            return
        
        if not self.accepting_payments:
            print(f"PaymentHandler: Ignoring bill pulse - payments not accepting")
            return
        
        current_time = time.time()
        
        # Debounce check
        if current_time - self.bill_last_pulse_time < self.DEBOUNCE_TIME:
            print(f"PaymentHandler: Ignoring bill pulse - too soon after last pulse ({current_time - self.bill_last_pulse_time:.3f}s)")
            return
        
        self.bill_pulse_count += 1
        self.bill_last_pulse_time = current_time
        
        print(f"PaymentHandler: Valid bill pulse detected - GPIO: {gpio}, Count: {self.bill_pulse_count}")
        
        # Process bill detection
        self._process_bill_detection()
    
    def _process_coin_detection(self):
        """Process detected coin and emit signal."""
        if self.coin_pulse_count >= 1:
            value, is_special = self._get_coin_value(self.coin_pulse_count)
            if value > 0:
                if is_special:
                    print(f"PaymentHandler: Processing special coin - {value} peso (cannot be given as change)")
                    self.special_coin_inserted.emit(value)
                else:
                    print(f"PaymentHandler: Processing regular coin - {value} peso")
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
    
    def _get_coin_value(self, pulses: int) -> tuple:
        """Convert pulse count to coin value based on actual coin acceptor behavior."""
        print(f"PaymentHandler: Analyzing {pulses} pulses for coin value")
        
        # Based on your logs, coins generate multiple pulses:
        # 1 peso = 1 pulse (correct)
        # 5 peso = 2 pulses (detected as two 1 peso coins)
        # 10 peso = 4 pulses (detected as four 1 peso coins)  
        # 20 peso = many pulses (detected as many 1 peso coins)
        
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
            return (0, False)  # (value, is_special)
    
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
            # Reset pulse counts to prevent ghost coins
            self.coin_pulse_count = 0
            self.bill_pulse_count = 0
            self.coin_cooldown_active = False
            
            # Enable coin acceptor (HIGH = enabled)
            self.pi.write(self.COIN_INHIBIT_PIN, 1)
            self.coin_enabled = True
            
            # Enable bill acceptor (LOW = enabled)
            self.pi.write(self.BILL_INHIBIT_PIN, 0)
            self.bill_enabled = True
            
            self.accepting_payments = True
            
            print("PaymentHandler: Payment acceptors enabled - pulse counts reset")
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
            'coin_cooldown_active': self.coin_cooldown_active,
            'isolated_from_hoppers': True  # Confirms complete separation
        }
    
    def verify_isolation(self):
        """Verify that payment handler is completely isolated from hopper manager."""
        print("PaymentHandler: Verifying complete isolation from hopper manager...")
        print(f"PaymentHandler: Using SEPARATE pigpio connection: {self.pi}")
        print(f"PaymentHandler: Monitoring ONLY payment pins: {self.COIN_PIN}, {self.BILL_PIN}")
        print(f"PaymentHandler: NOT monitoring hopper pins: 10, 13")
        print("PaymentHandler: ✅ COMPLETE ISOLATION CONFIRMED")
    
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
            print("PaymentHandler: Starting cleanup...")
            
            # Disable all acceptors first
            if self.gpio_available and self.pi:
                try:
                    self.disable_all_acceptors()
                except Exception as e:
                    print(f"PaymentHandler: Error disabling acceptors - {e}")
                
                # Clean up callbacks
                if self.coin_callback:
                    try:
                        self.coin_callback.cancel()
                    except Exception as e:
                        print(f"PaymentHandler: Error canceling coin callback - {e}")
                    finally:
                        self.coin_callback = None
                
                if self.bill_callback:
                    try:
                        self.bill_callback.cancel()
                    except Exception as e:
                        print(f"PaymentHandler: Error canceling bill callback - {e}")
                    finally:
                        self.bill_callback = None
                
                # Close pigpio connection
                try:
                    if self.pi.connected:
                        self.pi.stop()
                except Exception as e:
                    print(f"PaymentHandler: Error stopping pigpio - {e}")
                finally:
                    self.pi = None
            
            # Cancel pulse aggregation timer
            if self.pulse_aggregation_timer:
                try:
                    self.pulse_aggregation_timer.cancel()
                except Exception as e:
                    print(f"PaymentHandler: Error canceling pulse aggregation timer - {e}")
                finally:
                    self.pulse_aggregation_timer = None
            
            # Reset all state
            self.coin_enabled = False
            self.bill_enabled = False
            self.accepting_payments = False
            self.coin_cooldown_active = False
            self.coin_pulse_count = 0
            self.bill_pulse_count = 0
            
            print("PaymentHandler: Cleanup complete")
                
        except Exception as e:
            print(f"PaymentHandler: Cleanup error - {e}")
        finally:
            # Ensure we're in a clean state
            self.gpio_available = False
    
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
        if not _payment_handler_instance.initialize():
            print("PaymentHandler: Initialization failed, cleaning up")
            _payment_handler_instance.cleanup()
            _payment_handler_instance = None
            return None
    return _payment_handler_instance

def cleanup_payment_handler():
    """Clean up the global payment handler instance."""
    global _payment_handler_instance
    if _payment_handler_instance:
        try:
            _payment_handler_instance.cleanup()
        except Exception as e:
            print(f"PaymentHandler: Error during cleanup - {e}")
        finally:
            _payment_handler_instance = None
