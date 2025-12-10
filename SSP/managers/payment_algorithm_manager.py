from typing import Dict, Tuple
from database.db_manager import DatabaseManager

class PaymentAlgorithmManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        # Coin denominations available in the system
        self.COIN_DENOMINATIONS = [1, 5]  # ₱1 and ₱5 coins
    
    def get_coin_inventory(self) -> Dict[int, int]:
        """Fetch current coin counts from the database."""
        try:
            inventory = self.db_manager.get_cash_inventory()
            coin_inventory = {}
            
            for item in inventory:
                if item['type'] == 'coin' and item['denomination'] in self.COIN_DENOMINATIONS:
                    coin_inventory[item['denomination']] = item['count']
            
            # Ensure all denominations are present in the dict
            for denom in self.COIN_DENOMINATIONS:
                if denom not in coin_inventory:
                    coin_inventory[denom] = 0
                    
            return coin_inventory
        except Exception as e:
            print(f"Error getting coin inventory: {e}")
            return {1: 0, 5: 0}
    
    def check_strict_change(self, amount: float) -> Tuple[bool, Dict[int, int]]:
        """
        Strictly checks if change can be dispensed using a greedy approach 
        (Max 5s first, then 1s) without trying to "trade down".
        """
        if amount <= 0:
            return True, {1: 0, 5: 0}

        amount = int(round(amount))
        inventory = self.get_coin_inventory()
        
        # Available coins
        avail_5 = max(0, inventory.get(5, 0))
        avail_1 = max(0, inventory.get(1, 0))
        
        # Greedy Calculation: How many 5s do we ideally want?
        needed_5 = amount // 5
        
        # Take as many 5s as we actually have (up to needed amount)
        take_5 = min(needed_5, avail_5)
        
        # The remainder MUST be covered by 1s
        remainder = amount - (take_5 * 5)
        take_1 = remainder
        
        # Strict Verification: Do we have enough 1s?
        if take_1 <= avail_1:
            return True, {1: take_1, 5: take_5}
        else:
            return False, {1: take_1, 5: take_5}

    def can_dispense_change(self, change_amount: float) -> Tuple[bool, str, Dict[int, int]]:
        """
        Public method to check if change is possible. 
        Uses check_strict_change for consistency.
        """
        if change_amount <= 0:
            return True, "No change needed", {1: 0, 5: 0}
        
        # Use the strict checker for validation
        success, required_coins = self.check_strict_change(change_amount)
        
        if success:
            return True, "Change can be dispensed", required_coins
        else:
            # Re-fetch inventory just for the error message detail
            inv = self.get_coin_inventory()
            return False, (
                f"Insufficient coins for change ₱{int(change_amount)}. "
                f"Available: ₱5={inv.get(5,0)}, ₱1={inv.get(1,0)}"
            ), required_coins

    def get_payment_suggestion(self, total_cost: float) -> str:
        """
        Returns a string for the UI suggesting the best payment amount.
        Logic: Finds the smallest convenient amount (multiple of 5, 10, or bill) 
        >= total_cost that we can strictly dispense change for.
        """
        base = int(round(total_cost))
        
        # 1. Generate Candidates (Multiples of 5, 10, and Bills)
        candidates = set()
        
        # Next multiple of 5 (e.g. 22 -> 25)
        rem_5 = base % 5
        if rem_5 != 0:
            candidates.add(base + (5 - rem_5))
            
        # Next multiple of 10 (e.g. 9 -> 10, 22 -> 30)
        rem_10 = base % 10
        if rem_10 != 0:
            candidates.add(base + (10 - rem_10))
            
        # Common Bills/Coins (10, 20, 50, 100, 200, 500, 1000)
        # We check these specifically as they are likely user inputs
        for denom in [10, 20, 50, 100, 200, 500, 1000]:
            if denom > base:
                candidates.add(denom)
                
        # Sort to find the smallest convenient amount first
        sorted_candidates = sorted(list(candidates))
        
        # 2. Check Feasibility
        for amount in sorted_candidates:
            change_needed = amount - base
            # Use strict check to ensure we have the specific coins
            can, _ = self.check_strict_change(change_needed)
            if can:
                return f"Suggested: P{amount}"
                
        # 3. Fallback: If no convenient amount works, suggest Exact
        return f"Suggested: P{base} (Exact)"

    def find_best_payment_amount(self, total_cost: float) -> Dict:
        """
        Calculates the maximum bill the machine can accept.
        Kept for backward compatibility and internal limits.
        """
        # 1. Get Inventory
        coin_inventory = self.get_coin_inventory()
        
        # 2. Calculate Total Monetary Value of Inventory
        available_5 = max(0, coin_inventory.get(5, 0))
        available_1 = max(0, coin_inventory.get(1, 0))
        total_inventory_value = int((available_5 * 5) + available_1)
        
        # 3. Max change is strictly defined by total inventory
        max_possible_change = total_inventory_value

        # 4. Find the Real Mathematical Limit
        best_change = 0
        base = int(round(total_cost))

        for change in range(max_possible_change, -1, -1):
            can, _ = self.check_strict_change(change)
            if can:
                best_change = change
                break

        if best_change == 0:
            return {
                'amount': float(base),
                'change': 0.0,
                'required_coins': {1: 0, 5: 0},
                'reason': 'Exact payment'
            }

        ceiling = base + best_change
        chosen_amount = None
        chosen_required = None
        
        for amount in range(ceiling, base - 1, -1):
            if amount % 5 == 0:
                change_needed = amount - base
                can, req = self.check_strict_change(change_needed)
                if can:
                    chosen_amount = amount
                    chosen_required = req
                    break
        
        if chosen_amount is None:
            chosen_amount = base
            chosen_required = {1: 0, 5: 0}
            delta = 0
        else:
            delta = chosen_amount - base

        return {
            'amount': float(chosen_amount),
            'change': float(delta),
            'required_coins': chosen_required,
            'reason': ('Exact payment' if delta == 0 else f'Max payment: ₱{chosen_amount:.2f}')
        }