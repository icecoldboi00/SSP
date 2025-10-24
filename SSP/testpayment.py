#!/usr/bin/env python3
"""
Standalone Payment Acceptor Test Script

This script tests the coin and bill acceptors independently to verify:
- Pulse detection accuracy
- Ghost payment detection
- Proper coin/bill value recognition

GPIO Configuration:
- Coin Acceptor: Pin 5
- Bill Acceptor: Pin 18
- Coin Inhibit: Pin 22
- Bill Inhibit: Pin 23
"""

import time
import threading
import signal
import sys

# Check for pigpio availability
try:
    import pigpio
    PIGPIO_AVAILABLE = True
    print("✅ pigpio library found - Payment testing enabled")
except ImportError:
    PIGPIO_AVAILABLE = False
    print("❌ pigpio library not found - Payment testing disabled")
    sys.exit(1)


class PaymentTester:
    """Standalone payment acceptor tester."""
    
    def __init__(self):
        self.pi = None
        self.running = True
        
        # GPIO Pin Configuration (same as payment handler)
        self.COIN_PIN = 5          # Coin acceptor signal pin
        self.BILL_PIN = 18         # Bill acceptor signal pin
        self.COIN_INHIBIT_PIN = 22 # Coin acceptor control pin
        self.BILL_INHIBIT_PIN = 23 # Bill acceptor control pin
        
        # Pulse detection
        self.coin_pulse_count = 0
        self.bill_pulse_count = 0
        self.coin_last_pulse_time = 0
        self.bill_last_pulse_time = 0
        
        # Timing constants
        self.DEBOUNCE_TIME = 0.2      # Minimum time between pulses
        self.PULSE_AGGREGATION_TIMEOUT = 0.3  # Time to collect all pulses from one coin/bill
        
        # Aggregation timers
        self.coin_aggregation_timer = None
        self.bill_aggregation_timer = None
        
        # Callbacks
        self.coin_callback = None
        self.bill_callback = None
        
        # Test statistics
        self.test_start_time = time.time()
        self.total_coins_detected = 0
        self.total_bills_detected = 0
        self.ghost_detections = 0
        
        print("🔧 Payment Tester initialized")
        print(f"📌 Monitoring pins: Coin={self.COIN_PIN}, Bill={self.BILL_PIN}")
        print(f"📌 Control pins: Coin Inhibit={self.COIN_INHIBIT_PIN}, Bill Inhibit={self.BILL_INHIBIT_PIN}")
    
    def initialize(self):
        """Initialize GPIO connection and setup."""
        try:
            # Create pigpio connection
            self.pi = pigpio.pi()
            if not self.pi.connected:
                print("❌ Failed to connect to pigpio daemon")
                return False
            
            print("✅ Connected to pigpio daemon")
            
            # Setup GPIO pins
            self._setup_gpio_pins()
            
            # Enable both acceptors for testing
            self._enable_acceptors()
            
            print("✅ Payment test system ready")
            print("💰 Insert coins or bills to test detection...")
            print("🛑 Press Ctrl+C to stop testing")
            
            return True
            
        except Exception as e:
            print(f"❌ Initialization failed: {e}")
            return False
    
    def _setup_gpio_pins(self):
        """Setup GPIO pins for testing."""
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
            
            print(f"✅ GPIO pins configured - Coin: {self.COIN_PIN}, Bill: {self.BILL_PIN}")
            
        except Exception as e:
            print(f"❌ GPIO setup failed: {e}")
            raise
    
    def _enable_acceptors(self):
        """Enable both coin and bill acceptors for testing."""
        try:
            # Enable coin acceptor (HIGH = enabled)
            self.pi.write(self.COIN_INHIBIT_PIN, 1)
            print("✅ Coin acceptor enabled")
            
            # Enable bill acceptor (LOW = enabled)
            self.pi.write(self.BILL_INHIBIT_PIN, 0)
            print("✅ Bill acceptor enabled")
            
        except Exception as e:
            print(f"❌ Failed to enable acceptors: {e}")
    
    def _coin_pulse_detected(self, gpio, level, tick):
        """Handle coin pulse detection."""
        if gpio != self.COIN_PIN:
            print(f"⚠️  Ignoring pulse from GPIO {gpio} (not coin acceptor pin {self.COIN_PIN})")
            return
        
        current_time = time.time()
        
        # Debounce check
        if current_time - self.coin_last_pulse_time < self.DEBOUNCE_TIME:
            print(f"⚠️  Coin pulse ignored - too soon after last pulse ({current_time - self.coin_last_pulse_time:.3f}s)")
            return
        
        self.coin_pulse_count += 1
        self.coin_last_pulse_time = current_time
        
        print(f"🪙 Coin pulse detected - GPIO: {gpio}, Count: {self.coin_pulse_count}")
        
        # Start aggregation timer
        self._start_coin_aggregation()
    
    def _bill_pulse_detected(self, gpio, level, tick):
        """Handle bill pulse detection."""
        if gpio != self.BILL_PIN:
            print(f"⚠️  Ignoring pulse from GPIO {gpio} (not bill acceptor pin {self.BILL_PIN})")
            return
        
        current_time = time.time()
        
        # Debounce check
        if current_time - self.bill_last_pulse_time < self.DEBOUNCE_TIME:
            print(f"⚠️  Bill pulse ignored - too soon after last pulse ({current_time - self.bill_last_pulse_time:.3f}s)")
            return
        
        self.bill_pulse_count += 1
        self.bill_last_pulse_time = current_time
        
        print(f"💵 Bill pulse detected - GPIO: {gpio}, Count: {self.bill_pulse_count}")
        
        # Start aggregation timer
        self._start_bill_aggregation()
    
    def _start_coin_aggregation(self):
        """Start coin pulse aggregation timer."""
        if self.coin_aggregation_timer:
            self.coin_aggregation_timer.cancel()
        
        self.coin_aggregation_timer = threading.Timer(
            self.PULSE_AGGREGATION_TIMEOUT, 
            self._on_coin_aggregation_timeout
        )
        self.coin_aggregation_timer.start()
    
    def _start_bill_aggregation(self):
        """Start bill pulse aggregation timer."""
        if self.bill_aggregation_timer:
            self.bill_aggregation_timer.cancel()
        
        self.bill_aggregation_timer = threading.Timer(
            self.PULSE_AGGREGATION_TIMEOUT, 
            self._on_bill_aggregation_timeout
        )
        self.bill_aggregation_timer.start()
    
    def _on_coin_aggregation_timeout(self):
        """Process coin pulses when aggregation timeout occurs."""
        if self.coin_pulse_count > 0:
            value = self._get_coin_value(self.coin_pulse_count)
            if value > 0:
                self.total_coins_detected += 1
                print(f"💰 COIN DETECTED: {value} peso coin ({self.coin_pulse_count} pulses)")
                self._print_statistics()
            else:
                print(f"❓ Unknown coin pattern: {self.coin_pulse_count} pulses")
            
            # Reset pulse count
            self.coin_pulse_count = 0
        else:
            print("⚠️  Ghost coin detection - no pulses but timeout occurred")
            self.ghost_detections += 1
        
        self.coin_aggregation_timer = None
    
    def _on_bill_aggregation_timeout(self):
        """Process bill pulses when aggregation timeout occurs."""
        if self.bill_pulse_count > 0:
            value = self._get_bill_value(self.bill_pulse_count)
            if value > 0:
                self.total_bills_detected += 1
                print(f"💵 BILL DETECTED: {value} peso bill ({self.bill_pulse_count} pulses)")
                self._print_statistics()
            else:
                print(f"❓ Unknown bill pattern: {self.bill_pulse_count} pulses")
            
            # Reset pulse count
            self.bill_pulse_count = 0
        else:
            print("⚠️  Ghost bill detection - no pulses but timeout occurred")
            self.ghost_detections += 1
        
        self.bill_aggregation_timer = None
    
    def _get_coin_value(self, pulses: int) -> int:
        """Convert pulse count to coin value."""
        print(f"🔍 Analyzing {pulses} coin pulses...")
        
        if pulses == 1:
            return 1  # ₱1 coin = 1 pulse
        elif pulses == 2:
            return 5  # ₱5 coin = 2 pulses
        elif pulses == 4:
            return 10  # ₱10 coin = 4 pulses
        elif pulses >= 8:
            return 20  # ₱20 coin = 8+ pulses
        # Handle ranges for coins that might have slight variations
        elif 1 <= pulses <= 2:
            return 1 if pulses == 1 else 5  # ₱1 or ₱5 coin
        elif 3 <= pulses <= 5:
            return 10  # ₱10 coin with variation
        elif 6 <= pulses <= 10:
            return 20  # ₱20 coin with variation
        else:
            print(f"❓ Unknown coin pulse count: {pulses}")
            return 0
    
    def _get_bill_value(self, pulses: int) -> int:
        """Convert pulse count to bill value."""
        print(f"🔍 Analyzing {pulses} bill pulses...")
        
        if pulses == 2:
            return 20  # ₱20 bill = 2 pulses
        elif pulses == 5:
            return 50  # ₱50 bill = 5 pulses
        elif pulses == 10:
            return 100  # ₱100 bill = 10 pulses
        elif pulses == 50:
            return 500  # ₱500 bill = 50 pulses
        else:
            print(f"❓ Unknown bill pulse count: {pulses}")
            return 0
    
    def _print_statistics(self):
        """Print current test statistics."""
        runtime = time.time() - self.test_start_time
        print(f"📊 STATS: Runtime: {runtime:.1f}s | Coins: {self.total_coins_detected} | Bills: {self.total_bills_detected} | Ghost: {self.ghost_detections}")
    
    def run_test(self):
        """Run the payment test."""
        if not self.initialize():
            return
        
        try:
            print("\n" + "="*60)
            print("🧪 PAYMENT ACCEPTOR TEST STARTED")
            print("="*60)
            print("💰 Insert coins or bills to test detection")
            print("🛑 Press Ctrl+C to stop and show final statistics")
            print("="*60 + "\n")
            
            # Keep running until interrupted
            while self.running:
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            print("\n🛑 Test stopped by user")
        except Exception as e:
            print(f"\n❌ Test error: {e}")
        finally:
            self._cleanup()
            self._print_final_statistics()
    
    def _cleanup(self):
        """Clean up GPIO resources."""
        try:
            print("\n🧹 Cleaning up...")
            
            # Disable acceptors
            if self.pi:
                self.pi.write(self.COIN_INHIBIT_PIN, 0)  # Disable coin acceptor
                self.pi.write(self.BILL_INHIBIT_PIN, 1)  # Disable bill acceptor
                print("✅ Acceptors disabled")
            
            # Cancel timers
            if self.coin_aggregation_timer:
                self.coin_aggregation_timer.cancel()
            if self.bill_aggregation_timer:
                self.bill_aggregation_timer.cancel()
            
            # Clean up callbacks
            if self.coin_callback:
                self.coin_callback.cancel()
            if self.bill_callback:
                self.bill_callback.cancel()
            
            # Close pigpio connection
            if self.pi:
                self.pi.stop()
                print("✅ pigpio connection closed")
                
        except Exception as e:
            print(f"⚠️  Cleanup error: {e}")
    
    def _print_final_statistics(self):
        """Print final test statistics."""
        runtime = time.time() - self.test_start_time
        
        print("\n" + "="*60)
        print("📊 FINAL TEST STATISTICS")
        print("="*60)
        print(f"⏱️  Total Runtime: {runtime:.1f} seconds")
        print(f"🪙 Total Coins Detected: {self.total_coins_detected}")
        print(f"💵 Total Bills Detected: {self.total_bills_detected}")
        print(f"👻 Ghost Detections: {self.ghost_detections}")
        print(f"📈 Detection Rate: {(self.total_coins_detected + self.total_bills_detected) / (runtime / 60):.1f} items/minute")
        print("="*60)
        
        if self.ghost_detections > 0:
            print("⚠️  WARNING: Ghost detections detected!")
            print("   This may indicate hardware issues or interference.")
        else:
            print("✅ No ghost detections - system working correctly!")


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n🛑 Received interrupt signal")
    sys.exit(0)


def main():
    """Main function."""
    print("🧪 Payment Acceptor Test Script")
    print("=" * 40)
    
    # Set up signal handler for graceful exit
    signal.signal(signal.SIGINT, signal_handler)
    
    # Check pigpio availability
    if not PIGPIO_AVAILABLE:
        print("❌ pigpio library not available")
        print("   Please install: sudo apt-get install python3-pigpio")
        sys.exit(1)
    
    # Create and run tester
    tester = PaymentTester()
    tester.run_test()


if __name__ == "__main__":
    main()
