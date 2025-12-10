from typing import Dict, Tuple
from database.db_manager import DatabaseManager

class PaymentAlgorithmManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.COIN_DENOMINATIONS = [1, 5]  # ₱1 and ₱5 coins
    
    def get_coin_inventory(self) -> Dict[int, int]:
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

    def find_best_payment_amount(self, total_cost: float) -> Dict:
        """
        Calculates the maximum bill the machine can accept based purely on
        actual inventory and precise coin availability.
        """
        # 1. Get Inventory
        coin_inventory = self.get_coin_inventory()
        
        # 2. Calculate Total Monetary Value of Inventory
        available_5 = max(0, coin_inventory.get(5, 0))
        available_1 = max(0, coin_inventory.get(1, 0))
        total_inventory_value = int((available_5 * 5) + available_1)
        
        # 3. Max change is strictly defined by total inventory (No Admin Limit)
        max_possible_change = total_inventory_value

        # 4. Find the Real Mathematical Limit (The "Best Change")
        best_change = 0
        base = int(round(total_cost))

        # Search downwards for the highest possible change we can STRICTLY dispense
        for change in range(max_possible_change, -1, -1):
            can, _ = self.check_strict_change(change)
            if can:
                best_change = change
                break

        # 5. If absolutely no change is possible, force Exact Payment immediately
        if best_change == 0:
            return {
                'amount': float(base),
                'change': 0.0,
                'required_coins': {1: 0, 5: 0},
                'reason': 'Exact payment'
            }

        # 6. The "Clean Number" Logic (Snap to Grid)
        ceiling = base + best_change
        
        chosen_amount = None
        chosen_required = None
        
        # Search downwards from Ceiling to Cost
        for amount in range(ceiling, base - 1, -1):
            # Prefer multiples of 5 (e.g., 25, 30, 40) for cleaner user experience
            if amount % 5 == 0:
                change_needed = amount - base
                
                # Verify Reality: Can we actually dispense this specific change?
                can, req = self.check_strict_change(change_needed)
                
                if can:
                    chosen_amount = amount
                    chosen_required = req
                    break
        
        # 7. Fallback Logic (If no clean number found)
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
            'reason': (
                'Exact payment' if delta == 0
                else f'Max payment we can receive: ₱{chosen_amount:.2f}'
            )
        }