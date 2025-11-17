from PyQt5.QtCore import QObject, pyqtSignal
from database.db_manager import DatabaseManager

class AdminModel(QObject):
    paper_count_changed = pyqtSignal(int, str)  # New count and display color
    coin_count_changed = pyqtSignal(int, int)   # coin_1_count, coin_5_count
    cmyk_levels_changed = pyqtSignal(float, float, float, float)  # C M Y K
    show_message = pyqtSignal(str, str)         # Title and text

    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.paper_count = 100
        self.sms_alert_sent = False
        self._loading_cmyk = False  # Guard flag to prevent recursive call

    # Update paper count display
    def load_paper_count(self):
        self.paper_count = self.db_manager.get_setting('paper_count', default=100)
        print(f"AdminModel.load_paper_count: Loaded {self.paper_count} from database")
        color = self._get_color_for_count(self.paper_count)
        self.paper_count_changed.emit(self.paper_count, color)

    # Update coin count display
    def load_coin_counts(self): 
        inventory = self.db_manager.get_cash_inventory() # Return every row as dict
        coin_1_count = 0
        coin_5_count = 0
        
        for item in inventory:
            if item['denomination'] == 1 and item['type'] == 'coin':
                coin_1_count = item['count']
            elif item['denomination'] == 5 and item['type'] == 'coin':
                coin_5_count = item['count']
        
        self.coin_count_changed.emit(coin_1_count, coin_5_count)
        print(f"Coin counts loaded: ₱1={coin_1_count}, ₱5={coin_5_count}")

    # Update CMYK levels display
    def load_cmyk_levels(self): 
        if self._loading_cmyk:  
            return
            
        self._loading_cmyk = True # Set since about to start
        try:
            cmyk_data = self.db_manager.get_cmyk_ink_levels()
            if cmyk_data:
                self.cmyk_levels_changed.emit(
                    cmyk_data['cyan'], 
                    cmyk_data['magenta'], 
                    cmyk_data['yellow'], 
                    cmyk_data['black']
                )
                print(f"CMYK levels loaded: C:{cmyk_data['cyan']:.1f}% M:{cmyk_data['magenta']:.1f}% Y:{cmyk_data['yellow']:.1f}% K:{cmyk_data['black']:.1f}%")
            else:
                # No data available, set default values
                self.cmyk_levels_changed.emit(100.0, 100.0, 100.0, 100.0)
                print("No CMYK data found, using default values (100%)")
        except Exception as e:
            print(f"Error loading CMYK levels: {e}")
            self.cmyk_levels_changed.emit(100.0, 100.0, 100.0, 100.0)
        finally:
            self._loading_cmyk = False # Reset since about to end

    def reset_paper_count(self):
        self.paper_count = 100
        self.db_manager.update_setting('paper_count', self.paper_count)
        self.sms_alert_sent = False
        print("Paper count reset to 100, SMS alert flag also reset.")
        self.load_paper_count() # Reload to emit signal

    def increase_paper_count(self):
        if self.paper_count < 100:
            self.paper_count += 1
            self.db_manager.update_setting('paper_count', self.paper_count)
            color = self._get_color_for_count(self.paper_count)
            self.paper_count_changed.emit(self.paper_count, color)
            print(f"Paper count increased to {self.paper_count}")

    def decrease_paper_count(self):
        if self.paper_count > 0:
            self.paper_count -= 1
            self.db_manager.update_setting('paper_count', self.paper_count)
            color = self._get_color_for_count(self.paper_count)
            self.paper_count_changed.emit(self.paper_count, color)
            print(f"Paper count decreased to {self.paper_count}")

    # Called after printing to decrement database paper count
    def decrement_paper_count(self, pages_to_print: int) -> bool: # Pass int to parameter but function returns bool
        if self.paper_count >= pages_to_print:
            self.paper_count = max(0, self.paper_count - pages_to_print) # Prevent going negative
            self.db_manager.update_setting('paper_count', self.paper_count)
            self.check_low_paper_alert()
            self.load_paper_count() 
            print(f"Paper count decremented to {self.paper_count} sheets.")
            return True
        else:
            return False

    def check_low_paper_alert(self):
        if self.paper_count <= 10 and not self.sms_alert_sent:
            print(f"Low paper detected: {self.paper_count} sheets remaining. Sending alert.")
            try:
                from managers.sms_manager import send_low_paper_sms
                send_low_paper_sms()
                self.sms_alert_sent = True
                print("Low paper SMS sent successfully.")
            except Exception as e:
                print(f"Error sending SMS alert: {e}")

        elif self.paper_count > 10: # Reset alert if greater than 10
            self.sms_alert_sent = False 

    def reset_coin_counts(self):
        self.db_manager.update_cash_inventory(1, 100, 'coin')  # Default 100 ₱1 coins
        self.db_manager.update_cash_inventory(5, 50, 'coin')   # Default 50 ₱5 coins
        self.load_coin_counts()

    def increase_coin_1_count(self):
        inventory = self.db_manager.get_cash_inventory()
        current_count = 0
        for item in inventory:
            if item['denomination'] == 1 and item['type'] == 'coin':
                current_count = item['count']
                break
        
        if current_count < 200:  # Max limit
            new_count = current_count + 1
            self.db_manager.update_cash_inventory(1, new_count, 'coin')
            self.load_coin_counts()
            print(f"1 peso coin count increased to {new_count}")
        else: 
            print(f"1 peso coin count is at max limit of 200")

    def decrease_coin_1_count(self):
        inventory = self.db_manager.get_cash_inventory()
        current_count = 0
        for item in inventory:
            if item['denomination'] == 1 and item['type'] == 'coin':
                current_count = item['count']
                break
        
        if current_count > 0:  # Min limit
            new_count = current_count - 1
            self.db_manager.update_cash_inventory(1, new_count, 'coin')
            self.load_coin_counts()
            print(f"1 peso coin count decreased to {new_count}")
        else: 
            print(f"1 peso coin count is at min limit of 0")

    def increase_coin_5_count(self):
        inventory = self.db_manager.get_cash_inventory()
        current_count = 0
        for item in inventory:
            if item['denomination'] == 5 and item['type'] == 'coin':
                current_count = item['count']
                break
        
        if current_count < 200:  # Max limit
            new_count = current_count + 1
            self.db_manager.update_cash_inventory(5, new_count, 'coin')
            self.load_coin_counts()
            print(f"5 peso coin count increased to {new_count}")
        else:
            print(f"5 peso coin count is at max limit of 200")

    def decrease_coin_5_count(self):
        inventory = self.db_manager.get_cash_inventory()
        current_count = 0
        for item in inventory:
            if item['denomination'] == 5 and item['type'] == 'coin':
                current_count = item['count']
                break
        
        if current_count > 0:  # Min limit
            new_count = current_count - 1
            self.db_manager.update_cash_inventory(5, new_count, 'coin')
            self.load_coin_counts()
            print(f"₱5 coin count decreased to {new_count}")
        else:
            print(f"5 peso coin count is at min limit of 0")

    # On refresh button click
    def refresh_cmyk_levels(self): 
        self.load_cmyk_levels()

    # On update button click and if manual edits on the values are made
    def update_cmyk_levels(self, cyan: float, magenta: float, yellow: float, black: float):
        if not (0.0 <= cyan <= 100.0 and 0.0 <= magenta <= 100.0 and 
                0.0 <= yellow <= 100.0 and 0.0 <= black <= 100.0):
            self.show_message.emit("Invalid Input", "CMYK values must be between 0.0 and 100.0")
            self.load_cmyk_levels()
            return

        success = self.db_manager.update_cmyk_ink_levels(cyan, magenta, yellow, black) # Flag
        if success:
            self.load_cmyk_levels()
            print(f"CMYK levels updated: C:{cyan:.1f}% M:{magenta:.1f}% Y:{yellow:.1f}% K:{black:.1f}%")
            
            # Reset low ink alerts if levels are high (cartridges refilled)
            if cyan >= 95.0 and magenta >= 95.0 and yellow >= 95.0 and black >= 95.0:
                self._reset_ink_alerts()
        else:
            self.show_message.emit("Database Error", "Failed to update CMYK levels")
            
    def reset_cmyk_levels(self):
        success = self.db_manager.update_cmyk_ink_levels(100.0, 100.0, 100.0, 100.0)
        if success:
            self.load_cmyk_levels()
            print("CMYK levels reset to 100%")
            
            # Reset low ink alerts when cartridges are refilled
            self._reset_ink_alerts()
        else:
            self.show_message.emit("Database Error", "Failed to reset CMYK levels")

    # Reset flags in ink_analysis_manager after refilling cartridges
    def _reset_ink_alerts(self):
        from managers.ink_analysis_manager import InkAnalysisManager
        ink_manager = InkAnalysisManager(self.db_manager) # Flag 
        ink_manager.reset_low_ink_alerts()
        print("Low ink alert flags reset - cartridges refilled")

    # Change color based on paper count
    def _get_color_for_count(self, count: int) -> str: 
        if count <= 20: return "#dc3545"
        if count <= 50: return "#ffc107"
        return "#28a745"