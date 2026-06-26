import os
import sys
from typing import Union

class Config:
    def __init__(self):
        # 1. BULLETPROOF PATH: Find the exact folder where config.py lives
        base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Check inside the SSP folder
        ssp_env = os.path.join(base_dir, ".env")
        # Check the parent folder (SSP-fieldtest)
        parent_env = os.path.join(os.path.dirname(base_dir), ".env")
        
        if os.path.exists(parent_env):
            self.env_file = parent_env
        elif os.path.exists(ssp_env):
            self.env_file = ssp_env
        else:
            print(f"CRITICAL ERROR: .env file not found in {base_dir} or parent directory!")
            sys.exit(1)
            
        self._settings = {}
        self.reload()
    
    def reload(self):
        """Reads the file fresh from the hard drive, bypassing system caches."""
        self._settings.clear()
        print(f"DEBUG: Reloading config from exactly -> {self.env_file}")
        
        with open(self.env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if '#' in value:
                        value = value.split('#')[0].strip()
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Store in our local dictionary instead of the OS environment
                    self._settings[key] = value
    
    def get(self, key: str, value_type: type = str) -> Union[str, int, float, bool]:
        if key not in self._settings:
            raise KeyError(f"Configuration key '{key}' not found in {self.env_file}")
        
        value = self._settings[key]
        
        try:
            if value_type == bool:
                return str(value).lower() in ('true', '1', 'yes', 'on')
            elif value_type == int:
                return int(value)
            elif value_type == float:
                return float(value)
            else:
                return str(value)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Could not convert '{key}={value}' to {value_type.__name__}: {e}")
    
    # Page pricing configuration
    
    @property
    def black_and_white_price(self) -> float:
        return self.get('BLACK_AND_WHITE_PRICE', float)
    
    @property
    def color_price(self) -> float:
        return self.get('COLOR_PRICE', float)
    
    # Printer configuration
    
    @property
    def printer_name(self) -> str:
        return self.get('PRINTER_NAME', str)
    
    @property
    def printer_timeout(self) -> int:
        return self.get('PRINTER_TIMEOUT', int)
    
    @property
    def printer_retry_attempts(self) -> int:
        return self.get('PRINTER_RETRY_ATTEMPTS', int)
    
    # System settings
    
    @property
    def default_color_mode(self) -> str:
        return self.get('DEFAULT_COLOR_MODE', str)
    
    @property
    def max_copies(self) -> int:
        return self.get('MAX_COPIES', int)
    
    @property
    def min_copies(self) -> int:
        return self.get('MIN_COPIES', int)
    
    # Analysis settings
    
    @property
    def pdf_analysis_dpi(self) -> int:
        return self.get('PDF_ANALYSIS_DPI', int)
    
    @property
    def color_tolerance(self) -> int:
        return self.get('COLOR_TOLERANCE', int)
    
    @property
    def pixel_count_threshold(self) -> int:
        return self.get('PIXEL_COUNT_THRESHOLD', int)
    

    # Coin threshold settings
    @property
    def min_one_php_count(self) -> int:
        return self.get('MIN_ONE_PHP_COUNT', int)
    
    @property
    def min_five_php_count(self) -> int:
        return self.get('MIN_FIVE_PHP_COUNT', int)


    # Phone number configuration
    @property
    def phone_number(self) -> str:
        return self.get('PHONE_NUMBER', str)
    

    # Coin and Bill Pinouts
    
    @property
    def coin_pin(self) -> int:
        return self.get('COIN_PIN', int)
    
    @property
    def bill_pin(self) -> int:
        return self.get('BILL_PIN', int)
    
    @property
    def coin_inhibit_pin(self) -> int:
        return self.get('COIN_INHIBIT_PIN', int)
    
    @property
    def bill_inhibit_pin(self) -> int:
        return self.get('BILL_INHIBIT_PIN', int)
    
    
    # Display settings
    
    @property
    def force_fullscreen(self) -> bool:
        return self.get('FORCE_FULLSCREEN', bool)
    
    @property
    def window_width(self) -> int:
        return self.get('WINDOW_WIDTH', int)
    
    @property
    def window_height(self) -> int:
        return self.get('WINDOW_HEIGHT', int)
    
    @property
    def fullscreen_threshold_width(self) -> int:
        return self.get('FULLSCREEN_THRESHOLD_WIDTH', int)
    
    @property
    def fullscreen_threshold_height(self) -> int:
        return self.get('FULLSCREEN_THRESHOLD_HEIGHT', int)


# Global configuration instance
config = Config()


def get_config() -> Config:
    return config
