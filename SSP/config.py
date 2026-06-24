import os
import sys
from typing import Union


class Config:
    def __init__(self, env_file: str = ".env"):
        self.env_file = env_file
        self._check_env_file_exists()
        self._load_env_file()
    
    def _check_env_file_exists(self):
        if not os.path.exists(self.env_file):
            print(f"Configuration file '{self.env_file}' not found!")
            sys.exit(1)
    
    def _load_env_file(self):
        with open(self.env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue
                
                # Parse key=value pairs
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    # Remove inline comments (everything after #)
                    if '#' in value:
                        value = value.split('#')[0].strip()
                    
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    
                    # Set environment variable
                    os.environ[key] = value
    
    def get(self, key: str, value_type: type = str) -> Union[str, int, float, bool]:
        if key not in os.environ:
            raise KeyError(f"Configuration key '{key}' not found in .env file")
        
        value = os.environ[key]
        
        try:
            if value_type == bool:
                return value.lower() in ('true', '1', 'yes', 'on')
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
    

    # Phone number configuration
    @property
    def phone_number(self) -> str:
        return self.get('PHONE_NUMBER', str)
    
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
