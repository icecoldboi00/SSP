from typing import Dict, Tuple
from database.db_manager import DatabaseManager

class PaymentAlgorithmManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        # Coin denominations available in the system
        self.COIN_DENOMINATIONS = [1, 5]  # ₱1 and ₱5 coins

        # Read configurable thresholds from settings table (defaults allow dispensing with few coins)
        min_1 = self.db_manager.get_setting('min_coin_threshold_1', 0)
        min_5 = self.db_manager.get_setting('min_coin_threshold_5', 0)
        if isinstance(min_1, str):
            try:
                min_1 = int(min_1)
            except Exception:
                min_1 = 0
        if isinstance(min_5, str):
            try:
                min_5 = int(min_5)
            except Exception:
                min_5 = 0

        # Minimum thresholds for coin availability (reserve coins). Defaults to 0 so change works even with few coins.
        self.MIN_COIN_THRESHOLDS = {
            1: max(0, min_1),
            5: max(0, min_5)
        }

        # Maximum change that can be dispensed (configurable)
        max_change_cfg = self.db_manager.get_setting('max_change_limit', 50)
        try:
            self.MAX_CHANGE_LIMIT = float(max_change_cfg) if max_change_cfg is not None else 50.0
        except Exception:
            self.MAX_CHANGE_LIMIT = 50.0
    
    def get_coin_inventory(self) -> Dict[int, int]:
        try:
            inventory = self.db_manager.get_cash_inventory()
            coin_inventory = {}
            
            for item in inventory:
                if item['type'] == 'coin' and item['denomination'] in self.COIN_DENOMINATIONS:
                    coin_inventory[item['denomination']] = item['count']
            
            # Ensure all denominations are present
            for denom in self.COIN_DENOMINATIONS:
                if denom not in coin_inventory:
                    coin_inventory[denom] = 0
                    
            return coin_inventory
        except Exception as e:
            print(f"Error getting coin inventory: {e}")
            return {1: 0, 5: 0}
    
    def calculate_change_breakdown(self, change_amount: float) -> Dict[int, int]:
        if change_amount <= 0:
            return {1: 0, 5: 0}
        
        # Round to nearest peso (assuming no centavos in this system)
        change_amount = int(round(change_amount))
        
        # Greedy distribution without considering inventory
        coins_5 = int(change_amount // 5)
        coins_1 = int(change_amount % 5)
        
        return {1: coins_1, 5: coins_5}
    
    def can_dispense_change(self, change_amount: float) -> Tuple[bool, str, Dict[int, int]]:
        if change_amount <= 0:
            return True, "No change needed", {1: 0, 5: 0}
        
        # Get current coin inventory
        coin_inventory = self.get_coin_inventory()
        
        # Desired greedy breakdown
        desired = self.calculate_change_breakdown(change_amount)
        change_int = int(round(change_amount))
        
        # Try to make exact change with available coins
        use_fives = min(desired.get(5, 0), max(0, coin_inventory.get(5, 0)))
        remaining_after_fives = change_int - (use_fives * 5)
        if remaining_after_fives < 0:
            remaining_after_fives = 0
        use_ones = remaining_after_fives
        
        available_ones = max(0, coin_inventory.get(1, 0))
        
        # If not enough 1s to cover remainder, we can't dispense exact change
        # But we still accept the payment - just won't dispense change
        if use_ones > available_ones:
            return True, (
                f"Payment accepted. Cannot dispense exact change ₱{change_int} (only ₱{use_fives * 5 + available_ones} available). No change will be given."
            ), {1: 0, 5: 0}  # Return empty coins since we won't dispense
        
        required_coins = {1: use_ones, 5: use_fives}
        
        # Check minimum thresholds (reserve some coins for future transactions)
        # Only enforce when threshold > 0
        for denom, threshold in self.MIN_COIN_THRESHOLDS.items():
            if threshold and threshold > 0:
                remaining_after_change = coin_inventory.get(denom, 0) - required_coins.get(denom, 0)
                if remaining_after_change < threshold:
                    return True, f"Payment accepted. Cannot dispense change due to minimum reserve requirements. No change will be given.", {1: 0, 5: 0}  # Accept payment but no change
        
        return True, "Change can be dispensed", required_coins
    
    def find_best_payment_amount(self, total_cost: float) -> Dict:
        # We operate in whole pesos. Determine dynamic maximum change from inventory.
        coin_inventory = self.get_coin_inventory()
        th5 = self.MIN_COIN_THRESHOLDS.get(5, 0)
        th1 = self.MIN_COIN_THRESHOLDS.get(1, 0)
        available_5 = max(0, coin_inventory.get(5, 0) - (th5 if th5 > 0 else 0))
        available_1 = max(0, coin_inventory.get(1, 0) - (th1 if th1 > 0 else 0))
        max_possible_change = int((available_5 * 5) + available_1)

        best_change = 0

        base = int(round(total_cost))
        for change in range(max_possible_change, -1, -1):
            can, _, _ = self.can_dispense_change(change)
            if can:
                best_change = change
                break

        # If no change is possible, return exact
        if best_change == 0:
            return {
                'amount': float(base),
                'change': 0.0,
                'required_coins': {1: 0, 5: 0},
                'reason': 'Exact payment'
            }

        ceiling = base + best_change
        accepted = [1, 5, 10, 20, 50, 100]
        # Filter to realistic denominations within [total_cost, ceiling]
        viable = [d for d in accepted if d >= base and d <= ceiling]
        viable.sort()

        chosen_amount = None
        chosen_required = None
        # Try largest first, also validate change feasibility for that denomination
        for d in reversed(viable):
            change_needed = d - base
            if change_needed < 0:
                continue
            can, _, req = self.can_dispense_change(change_needed)
            if can:
                chosen_amount = d
                chosen_required = req
                break

        if chosen_amount is None:
            # Fallback to exact if no denomination fits
            chosen_amount = base
            chosen_required = {1: 0, 5: 0}
            delta = 0
        else:
            delta = chosen_amount - base

        return {
            'amount': float(chosen_amount),
            'change': float(delta),
            'required_coins': chosen_required,
            'reason': (
                'Exact payment' if delta == 0
                else f'Max payment we can receive: ₱{chosen_amount:.2f} (available ₱{delta:.2f})'
            )
        }
