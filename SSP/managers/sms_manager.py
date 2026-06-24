import serial
import time
from PyQt5.QtCore import QObject
from config import get_config

class SMSManager(QObject):
    def __init__(self, serial_port="/dev/serial0", baudrate=9600):
        super().__init__()
        config = get_config()
        self.phone_number = config.phone_number
        self.serial_port = serial_port
        self.baudrate = baudrate
    
    def send_sms(self, message):
        try:
            print("Starting modem...")
            # Give modem time to boot up
            time.sleep(5)
            
            # Open serial connection
            ser = serial.Serial(self.serial_port, baudrate=self.baudrate, timeout=1)
            
            # Basic AT check
            ser.write(b'AT\r')
            time.sleep(1)
            ser.read(100)  # Clear response buffer
            
            # Set SMS to text mode
            ser.write(b'AT+CMGF=1\r')
            time.sleep(1)
            ser.read(100)  # Clear response buffer
            
            # Set the recipient's phone number and wait for prompt
            cmd = f'AT+CMGS="{self.phone_number}"\r'
            ser.write(cmd.encode())
            time.sleep(1)
            
            # Wait for the ">" prompt from the modem before sending message
            prompt_received = False
            timeout = 5
            start_time = time.time()
            while time.time() - start_time < timeout:
                if ser.in_waiting > 0:
                    response = ser.read(ser.in_waiting).decode(errors="ignore")
                    if ">" in response:
                        prompt_received = True
                        break
                time.sleep(0.1)
            
            if not prompt_received:
                print("Warning: Did not receive '>' prompt from modem")
            
            # Now send the message followed by Ctrl+Z (0x1A)
            ser.write(message.encode() + bytes([26]))
            ser.flush()
            
            # Wait for the final response
            time.sleep(15)
            response = ser.read(500).decode(errors="ignore").strip()
            
            if "+CMGS:" in response and "OK" in response:
                print("Message sent successfully!")
                return True
            else:
                print("Failed to send message.")
                return False
                
        except serial.SerialException as e:
            print(f"Serial error: {e}")
            return False
        except Exception as e:
            print(f"An error occurred: {e}")
            return False
        finally:
            # Close the serial port
            if 'ser' in locals() and ser.is_open:
                ser.close()
                print("Serial port closed.")

# Global SMS manager instance
sms_manager = None

def get_sms_manager():
    global sms_manager
    if sms_manager is None:
        sms_manager = SMSManager()
    return sms_manager

def send_no_paper_sms():
    manager = get_sms_manager()
    return manager.send_sms("No paper, please refill.")

def send_low_paper_sms():
    manager = get_sms_manager()
    return manager.send_sms("Low paper, please refill.")

def send_paper_jam_sms():
    manager = get_sms_manager()
    return manager.send_sms("Printer jam")

def send_printing_error_sms(error_message):
    manager = get_sms_manager()
    return manager.send_sms(f"Printing error: {error_message}")

def send_low_ink_sms(ink_type, level):
    manager = get_sms_manager()
    message = f"{ink_type} ink is low ({level:.1f}%). Please refill soon."
    return manager.send_sms(message)

def send_multiple_low_ink_sms(low_cartridges):
    manager = get_sms_manager()
    cartridge_list = ", ".join([f"{cartridge} ({level:.1f}%)" for cartridge, level in low_cartridges])
    message = f"Multiple ink cartridges are low - {cartridge_list}. Please refill soon."
    return manager.send_sms(message)

def send_low_coin_sms(coin_type, count):
    manager = get_sms_manager()
    safe_label = str(coin_type)
    message = f"Low on {safe_label} coins ({count} remaining). Please refill soon."
    return manager.send_sms(message)

def send_multiple_low_coins_sms(low_coins):
    manager = get_sms_manager()
    coin_list = ", ".join([f"{str(coin_type)} ({count} remaining)" for coin_type, count in low_coins])
    message = f"Multiple coin types are low - {coin_list}. Please refill soon."
    return manager.send_sms(message)

def cleanup_sms():
    global sms_manager
    sms_manager = None
