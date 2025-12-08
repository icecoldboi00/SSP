import pigpio
import time
from PyQt5.QtCore import QThread, pyqtSignal
from database.db_manager import DatabaseManager

COIN_DELAY = 1.5         # Delay after a successful dispense before next one
DISPENSING_TIMEOUT = 10  # Maximum time to wait for a single coin
MAX_RETRY_ATTEMPTS = 3   # Maximum attempts per coin before giving up 
RETRY_DELAY = 1.0        # Delay between retry attempts

HOPPER_CONFIGS = {
    'A': {
        'signal_pin': 9,  # Coin pulse input for 1 Peso
        'enable_pin': 24   # Hopper enable control 
    },
    'B': {
        'signal_pin': 26,   # Coin pulse input for 5 Peso
        'enable_pin': 25   # Hopper enable control 
    }
}


class HopperController:
    def __init__(self, pi_instance, name, signal_pin, enable_pin):
        self.pi = pi_instance

        self.name = name
        self.signal_pin = signal_pin
        self.enable_pin = enable_pin

        self.enabled = False
        self.dispensing = False

        # Passage tracking
        self.sensor_active = False
        self.coin_passage_count = 0
        self.last_sensor_change = 0

        self.pi.set_mode(self.signal_pin, pigpio.INPUT)
        self.pi.set_pull_up_down(self.signal_pin, pigpio.PUD_UP)
        self.pi.set_mode(self.enable_pin, pigpio.OUTPUT)

        # Monitor both rising and falling edges to track coin passage
        # Each instance will have its own callback tied to its specific signal pin
        self.callback = self.pi.callback(self.signal_pin, pigpio.EITHER_EDGE, self._sensor_callback)

        self._disable_hopper()
        print(f"[{self.name}] hopper setup completed successfully")

    def cleanup(self):
        try:
            # First disable the hopper to stop any ongoing operations
            if getattr(self, 'pi', None) and hasattr(self.pi, 'connected') and self.pi.connected:
                self._disable_hopper()
                print(f"[{self.name}] Hopper disabled during cleanup")
            elif getattr(self, 'pi', None) is None:
                print(f"[{self.name}] No pigpio connection to clean up")
            
            # Then cancel the callback
            if getattr(self, 'callback', None):
                try:
                    self.callback.cancel()
                    self.callback = None
                    print(f"[{self.name}] Callback cleaned up")
                except Exception as callback_error:
                    print(f"[{self.name}] Error canceling callback: {callback_error}")
            
            # Clear pigpio instance reference to avoid later use in callbacks
            self.pi = None
                
        except Exception as e:
            print(f"[{self.name}] Error during cleanup: {e}")

    def _enable_hopper(self):
        if not self.pi or not self.pi.connected:
            print(f"[{self.name}] ERROR: pigpio connection not available")
            return False
        try:
            self.pi.write(self.enable_pin, 0) # Active low
            self.enabled = True
            print(f"[{self.name}] Hopper motor ENABLED")
            return True
        except Exception as e:
            print(f"[{self.name}] Failed to enable hopper: {e}")
            return False

    def _disable_hopper(self):
        if not self.pi or not self.pi.connected:
            print(f"[{self.name}] pigpio connection not available")
            return False
        try:
            self.pi.write(self.enable_pin, 1) # Inactive high
            self.enabled = False
            print(f"[{self.name}] Hopper motor DISABLED")
            return True
        except Exception as e:
            print(f"[{self.name}] Failed to disable hopper: {e}")
            return False

    def _sensor_callback(self, gpio, level, tick):
        # Guard against callbacks firing after pigpio connection is closed
        try:
            if not self.pi or not getattr(self.pi, 'connected', False):
                return
            current_time = self.pi.get_current_tick()
        except Exception:
            # pigpio thread may still invoke callbacks during shutdown; ignore safely
            return

        if level == 0:  # Falling edge - coin detected
            if not self.sensor_active:
                self.sensor_active = True
                self.last_sensor_change = current_time
        else:  # Rising edge - coin cleared
            if self.sensor_active:
                self.sensor_active = False
                # pigpio tick is a 32-bit unsigned int, handle wraparound
                elapsed = pigpio.tickDiff(self.last_sensor_change, current_time) / 1000000.0
                if elapsed > 0.01:  # Debounce: Minimum time for valid coin passage (10ms)
                    self.coin_passage_count += 1
                

    def _wait_for_coin_passage(self):
        print(f"[{self.name}] Waiting for exactly one coin")
        # Reset detection counters for this attempt
        self.coin_passage_count = 0
        self.sensor_active = False

        timeout_start = time.time()
        while (time.time() - timeout_start) < DISPENSING_TIMEOUT: # Spin hopper 10 seconds until coin pass
            if self.coin_passage_count == 1:
                print(f"[{self.name}] one coin pass")
                return True
            if self.coin_passage_count > 1:
                print(f"[{self.name}] multiple coins detected ({self.coin_passage_count})! Stopping motor.")
                return False
            time.sleep(0.01)

        # Last check if coin pass
        if self.coin_passage_count == 1:
            print(f"[{self.name}] one coin pass")
            return True
        else:
            print(f"[{self.name}] timeout. Found {self.coin_passage_count} passages.")
            return False

    def _dispense_single_coin_attempt(self):
        self._enable_hopper()

        success = self._wait_for_coin_passage()

        self._disable_hopper()

        return success

    def dispense_single_coin(self):
        if self.dispensing:
            return False
            
        self.dispensing = True
        print(f"\n--- [{self.name}] Dispensing 1 coin ---")

        attempt = 1
        success = False
        while attempt <= MAX_RETRY_ATTEMPTS:
            print(f"[{self.name}] Attempt {attempt}/{MAX_RETRY_ATTEMPTS}...")
            if self._dispense_single_coin_attempt():
                print(f"[{self.name}] Coin dispensed and verified on attempt {attempt}.")
                success = True
                break
            else:
                print(f"[{self.name}] Attempt {attempt} was unsuccessful.")
                if self.coin_passage_count > 1:
                    print(f"[{self.name}] Dispensed too many coins. Aborting.")
                    break # Don't retry if we over-dispensed
                if attempt < MAX_RETRY_ATTEMPTS:
                    print(f"[{self.name}] Retrying in {RETRY_DELAY}s...")
                    time.sleep(RETRY_DELAY)
            attempt += 1

        if not success:
            print(f"[{self.name}] Could not dispense a single coin after {MAX_RETRY_ATTEMPTS} attempts.")

        # Brief pause to allow system to settle before next command
        time.sleep(COIN_DELAY)
        self.dispensing = False
        return success

class ChangeDispenser:
    def __init__(self):
        self.pi = None
        self.hoppers = {}

        self.pi = pigpio.pi()
        
        # Create a controller for each hopper defined in config
        for name, config in HOPPER_CONFIGS.items():
            self.hoppers[name] = HopperController(
                pi_instance=self.pi,
                name=name,
                signal_pin=config['signal_pin'],
                enable_pin=config['enable_pin']
            )

    def dispense_change(self, amount: float, status_callback=None, required_coins=None):
        if amount <= 0:
            return {'success': True, 'coins_1': 0, 'coins_5': 0}

        # Determine available inventory from database using a fresh connection (thread-safe)
        available_fives = None
        available_ones = None
        try:
            dbm = DatabaseManager()
            inventory = dbm.get_cash_inventory()
            available_fives = 0
            available_ones = 0
            for item in inventory:
                if item.get('type') == 'coin' and item.get('denomination') == 5:
                    available_fives = int(item.get('count', 0))
                elif item.get('type') == 'coin' and item.get('denomination') == 1:
                    available_ones = int(item.get('count', 0))
        except Exception as e:
            print(f"Could not read coin inventory with fresh DB connection: {e}")
            available_fives = None
            available_ones = None

        # Use provided breakdown if available, otherwise compute greedy
        if isinstance(required_coins, dict):
            desired_fives = int(required_coins.get(5, 0))
            desired_ones = int(required_coins.get(1, 0))
        else:
            # Greedy target breakdown for the amount
            desired_fives = int(amount // 5)
            desired_ones = int(amount % 5)

        # Cap by availability when inventory known
        if available_fives is not None and available_ones is not None:
            num_fives = min(desired_fives, max(0, available_fives))
            remaining_value = int(amount - (num_fives * 5))
            num_ones = min(desired_ones if isinstance(required_coins, dict) else remaining_value, max(0, available_ones))

            # Evaluate if exact change is possible with capped counts
            disp_value = (num_fives * 5) + num_ones
            total_available_value = (available_fives * 5) + available_ones

            if disp_value < int(amount):
                # Not enough coins to make exact change
                if total_available_value <= 0:
                    print("No coins available in database. No dispense.")
                    return {'success': True, 'coins_1': 0, 'coins_5': 0, 'actual_change': 0, 'expected_change': int(amount)}
                
                # FIXED: Logic removed that previously set num_fives/num_ones to ALL available coins.
                # We now keep the partial amounts calculated above.
                print(f"Insufficient coins for exact change. Dispensing partial amount: P{disp_value} (Target: P{amount})")
        else:
            # Inventory unknown; proceed with desired targets
            num_fives = desired_fives
            num_ones = desired_ones
        
        print(f"Dispensing 'P{amount:.2f}: {num_fives}x 5-peso, {num_ones}x 1-peso")
        if status_callback:
            status_callback(f"Preparing to dispense ₱{amount:.2f}...")

        # Track actual coins dispensed
        actual_fives = 0
        actual_ones = 0

        # Dispense 5-peso coins
        for i in range(num_fives):
            msg = f"Dispensing 5-peso coin ({i + 1} of {num_fives})"
            if status_callback: status_callback(msg)
            print(msg)

            success = self.hoppers['B'].dispense_single_coin()

            if success:
                actual_fives += 1
            else:
                # Continue and try to make up with ₱1 coins later
                continue

        # Include makeup ones for any missing ₱5s
        makeup_ones = max(0, (num_fives - actual_fives) * 5)
        total_ones_to_dispense = num_ones + makeup_ones
        if makeup_ones > 0:
            print(f"Making up short ₱5 coins with {makeup_ones} ₱1 coins")

        # Dispense 1-peso coins
        for i in range(total_ones_to_dispense):
            msg = f"Dispensing 1-peso coin ({i + 1} of {total_ones_to_dispense})"
            if status_callback: status_callback(msg)
            print(msg)
            
            success = self.hoppers['A'].dispense_single_coin()

            if success:
                actual_ones += 1
            else:
                # Continue with what we have instead of failing completely
                break
        
        # Calculate actual change dispensed
        actual_change = (actual_fives * 5) + (actual_ones * 1)
        expected_change = (num_fives * 5) + (num_ones * 1)

        
        final_msg = f"Change dispensing complete. Dispensed P{actual_change:.2f} (P{actual_fives}x5 + P{actual_ones}x1) of P{expected_change:.2f} expected."
        if status_callback: status_callback(final_msg)
        print(final_msg)
        
        return {
            'success': True,
            'coins_1': actual_ones,
            'coins_5': actual_fives,
            'actual_change': actual_change,
            'expected_change': expected_change
        }

    def cleanup(self):
        if self.pi:
            # Clean up all hoppers
            for name, hopper in self.hoppers.items():
                try:
                    hopper.cleanup()
                    print(f"[{name}] Hopper cleaned up")
                except Exception as e:
                    print(f"[{name}] Error cleaning up hopper: {e}")
            self.hoppers.clear()
            
            try:
                self.pi.stop()
                print("pigpio connection stopped.")
            except Exception as e:
                print(f"Error stopping pigpio connection: {e}")
            finally:
                self.pi = None

    def __del__(self):
        self.cleanup()


class DispenseThread(QThread):
    status_update = pyqtSignal(str)
    dispensing_finished = pyqtSignal(dict)  # Changed to emit the full result dict

    def __init__(self, dispenser: ChangeDispenser, amount: float, required_coins=None):
        super().__init__()
        self.dispenser = dispenser
        self.amount = amount
        self.required_coins = required_coins

    def run(self):
        if self.dispenser is None:
            print("ERROR: Dispenser is None, cannot dispense change")
            result = {
                'success': False, 
                'coins_1': 0, 
                'coins_5': 0, 
                'error': 'dispenser_not_available'
            }
            self.dispensing_finished.emit(result)
            return
            
        result = self.dispenser.dispense_change(
            self.amount,
            self.status_update.emit,
            required_coins=self.required_coins
        )
        self.dispensing_finished.emit(result)