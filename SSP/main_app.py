import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt5.QtCore import Qt
from screens.idle import IdleController
from screens.usb import USBController
from screens.file_browser import FileBrowserController
from screens.payment import PaymentController
from screens.print_options import PrintOptionsController
from screens.admin import AdminController
from screens.data_viewer import DataViewerController
from screens.thank_you import ThankYouController
from database.models import init_db
from managers.usb_file_manager import USBFileManager
from managers.printer_manager import PrinterManager
from managers.sms_manager import cleanup_sms



class PrintingSystemApp(QMainWindow):
    # Screen index mapping for stacked widget navigation
    SCREEN_MAP = {
        'idle': 0,
        'usb': 1,
        'file_browser': 2,
        'printing_options': 3,
        'payment': 4,
        'admin': 5,
        'data_viewer': 6,
        'thank_you': 7
    }
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Printing System GUI")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setGeometry(100, 100, 1024, 600)
        self.setMinimumSize(1024, 600)
        self.setStyleSheet("""
            QMainWindow {
                background-color: transparent;
            }
        """)
        
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.printer_manager = PrinterManager()
        self.usb_file_manager = USBFileManager()
        self.low_paper_alert_sent = False

        self.idle_screen = IdleController(self)
        self.usb_screen = USBController(self)
        self.file_browser_screen = FileBrowserController(self)
        self.printing_options_screen = PrintOptionsController(self)
        self.payment_screen = PaymentController(self)
        self.admin_screen = AdminController(self)
        self.data_viewer_screen = DataViewerController(self, self.admin_screen.db_manager)
        self.thank_you_screen = ThankYouController(self)

        # Must be in order of SCREEN_MAP
        self.stacked_widget.addWidget(self.idle_screen)
        self.stacked_widget.addWidget(self.usb_screen)
        self.stacked_widget.addWidget(self.file_browser_screen)
        self.stacked_widget.addWidget(self.printing_options_screen)
        self.stacked_widget.addWidget(self.payment_screen)
        self.stacked_widget.addWidget(self.admin_screen)
        self.stacked_widget.addWidget(self.data_viewer_screen)
        self.stacked_widget.addWidget(self.thank_you_screen)

        # Cross thread signals between main app and printer manager
        self.printer_manager.print_job_successful.connect(self.on_print_successful, Qt.QueuedConnection)
        self.printer_manager.print_job_failed.connect(self.on_print_failed, Qt.QueuedConnection)
        self.printer_manager.print_job_waiting.connect(self.thank_you_screen.show_waiting_for_print, Qt.QueuedConnection)
        self.payment_screen.payment_completed.connect(self.on_payment_completed)

        self.show_screen('idle')
    
    # Paper count check and redirect if low
    def check_paper_count_and_redirect(self):
        paper_count = self.admin_screen.get_paper_count()
        if paper_count <= 3:  # Stop kiosk at 3 pages
            print(f"Low paper detected: {paper_count} pages remaining. Redirecting to error screen.")
            self.show_screen('thank_you')
            self.thank_you_screen.show_no_paper_error(paper_count)
            return True  # Redirect to error screen
        return False  # Continue normally

    # Ink level check and redirect if any cartridge is critically low
    def check_ink_levels_and_redirect(self):
        try:
            cmyk_levels = self.admin_screen.db_manager.get_cmyk_ink_levels()
            if not cmyk_levels:
                print("No CMYK ink data available, skipping ink level kiosk check")
                return False

            low_ink_threshold = 20.0
            low_cartridges = {
                name: level
                for name, level in cmyk_levels.items()
                if name in ('cyan', 'magenta', 'yellow', 'black') and level <= low_ink_threshold
            }

            if low_cartridges:
                details = ", ".join(f"{name.capitalize()}: {level:.1f}%" for name, level in low_cartridges.items())
                print(f"Critical low ink detected ({details}). Disabling kiosk and redirecting to error screen.")
                # Redirect to thank you / error screen and show a clear low-ink message
                self.show_screen('thank_you')
                self.thank_you_screen.show_printing_error(
                    "Ink levels are too low to continue printing.\n"
                    "Please contact an administrator to replace the ink cartridges."
                )
                return True

            return False
        except Exception as e:
            print(f"Error checking ink levels for kiosk disabling: {e}")
            return False
        
    # Coin level check and redirect if either 1-peso or 5-peso coins drop below the threshold
    def check_coin_levels_and_redirect(self):
        from config import get_config

        config = get_config()
        try:
            # Fetch the current cash inventory from the database
            inventory = self.admin_screen.db_manager.get_cash_inventory()
            coins = {1: 0, 5: 0}
            
            for item in inventory:
                if item.get('type') == 'coin':
                    denom = int(item.get('denomination'))
                    if denom in coins:
                        coins[denom] = int(item.get('count', 0))
            
            # Check if either 1-peso or 5-peso coins drop below the threshold
            if coins[1] <= config.min_one_php_count or coins[5] <= config.min_five_php_count:
                print(f"Low coins detected! ₱1: {coins[1]}, ₱5: {coins[5]}. Redirecting to error screen.")
                self.show_screen('thank_you')
                self.thank_you_screen.show_low_coins_error(coins[1], coins[5])
                return True
                
            return False
        except Exception as e:
            print(f"Error checking coin levels: {e}")
            return False

    # Show screen method and calling on_leave and on_enter methods
    def show_screen(self, screen_name):
        # Call on_leave method for current screen
        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'on_leave'):
            current_widget.on_leave()

        # Check paper count before switching to most screens (except admin and thank_you)
        if screen_name not in ['admin', 'thank_you']:
            if self.check_paper_count_and_redirect():
                print(f"Cannot navigate to {screen_name} - insufficient paper")
                return
            
            # Check coin levels to block starting new sessions if low
            if self.check_coin_levels_and_redirect():
                print(f"Cannot navigate to {screen_name} - insufficient coins for change")
                return
        
        # Switch to the new screen
        target_index = self.SCREEN_MAP[screen_name]
        self.stacked_widget.setCurrentIndex(target_index)
        
        # Call on_enter method for new screen
        next_widget = self.stacked_widget.currentWidget()
        if hasattr(next_widget, 'on_enter'):
            next_widget.on_enter()
 

    def on_payment_completed(self, payment_info):
        self.current_payment_info = payment_info
        
        # Show thank you screen after payment
        self.show_screen('thank_you')
        
        # Get file path for print job
        file_path = payment_info['pdf_data']['path']
        
        # Check printer availability before starting print job
        if not self.printer_manager.check_printer_availability():
            self.thank_you_screen.show_printing_error("Printer is not available. Please check printer connection.")
            return
        
        # Store print job details for thank you screen
        self.current_print_job = {
            'file_path': file_path,
            'selected_pages': payment_info['selected_pages'],
            'copies': payment_info['copies'],
            'color_mode': payment_info['color_mode']
        }
        print(f"Print job details stored")
        
        # Start print job
        try:
            self.printer_manager.print_file(
                file_path=file_path,
                copies=payment_info['copies'],
                color_mode=payment_info['color_mode'],
                selected_pages=payment_info['selected_pages']
            )
            print(f"Print job started successfully")
        except Exception as e:
            print(f"Error starting print job: {e}")
            self.thank_you_screen.show_printing_error(f"Failed to start print job: {str(e)}")

 
    def on_print_successful(self):
        # Update paper count before clearing print job info
        self._update_paper_count_after_print()
        
        # Clean up session directory - ONLY on success
        self.usb_file_manager.cleanup_session_directory()
        
        # Trigger ink analysis before clearing print job info
        if self.current_print_job:
            self.printer_manager.trigger_ink_analysis(self.current_print_job['copies'])
        
        # Clear the print job to prevent re-printing
        self.current_print_job = None
        
        current_screen = self.stacked_widget.currentWidget()
        
        if current_screen == self.idle_screen:
            print("Print completed while on idle screen - no action needed")
        elif current_screen != self.thank_you_screen:
            print(f"Print completed on wrong screen, navigating to thank you screen")
            self.show_screen('thank_you')

    def _update_paper_count_after_print(self):
        # Check if print job info exists
        if not self.current_print_job:
            print("No print job info available for ink analysis")
            return
        
        try:
            # Calculate total pages printed
            selected_pages = self.current_print_job.get('selected_pages', [])
            copies = self.current_print_job.get('copies', 1)
            total_pages = len(selected_pages) * copies
            
            print(f"Decrementing paper count: -{total_pages} pages")
            
            success = self.admin_screen.model.decrement_paper_count(total_pages)
            
            if success:
                updated_count = self.admin_screen.get_paper_count()
                print(f"Paper count updated to: {updated_count}")
                
                if updated_count <= 10 and not self.low_paper_alert_sent:
                    print(f"Low paper alert flag set: {updated_count} sheets remaining")
                    self.low_paper_alert_sent = True
                elif updated_count > 10:
                    self.low_paper_alert_sent = False
            else:
                print("Failed to update paper count")
                
        except Exception as e:
            print(f"Error updating paper count: {e}")


    def on_print_failed(self, error_message):
        print(f"Print job failed: {error_message}")
        
        # Send SMS notification for all print failures
        try:
            from managers.sms_manager import send_printing_error_sms
            send_printing_error_sms(error_message)
        except Exception as sms_error:
            print(f"Failed to send SMS notification: {sms_error}")
        
        # Log error to database
        try:
            from utils.error_logger import log_error
            log_error("Printing Error", error_message, "main_app")
        except Exception as db_error:
            print(f"Failed to log error to database: {db_error}")
        
        # Display error on thank you screen
        if self.stacked_widget.currentWidget() == self.thank_you_screen:
            # Check if this is a paper jam error for specialized handling
            if "paper jam" in error_message.lower() or "jam" in error_message.lower():
                self.thank_you_screen.show_paper_jam_error(error_message)
            else:
                self.thank_you_screen.show_printing_error(error_message)
        else:
            print(f"Print failed on wrong screen. Error: {error_message}")

    # Clean up resources before closing window
    def cleanup(self):
        try:
            print("Starting cleanup")

            # Clean up printer manager (includes ink analysis thread)
            self.printer_manager.cleanup()

            self.usb_screen.model.stop_usb_monitoring()

            cleanup_sms()
            
            # Ensure files are cleaned up when the app actually closes
            self.usb_file_manager.cleanup_session_directory()

            try:
                from utils.error_logger import cleanup_db_connections
                print("Cleaning up database connections")
                cleanup_db_connections()
            except Exception as db_cleanup_error:
                print(f"Error cleaning up database connections: {db_cleanup_error}")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")

    # Cleanup when window is closed just for safety while testing
    def closeEvent(self, event): 
        self.cleanup()
        event.accept()


def main():
    try:
        init_db()
        print("Database initialization successful\n")
    
        # Create Qt application
        app = QApplication(sys.argv) # Main thread init
        app.setApplicationName("Printing System GUI")
        app.setApplicationVersion("1.21")
        window = PrintingSystemApp()

        # Show window (size and mode determined by _setup_display)
        window.showFullScreen()
        
        # Set up cleanup on exit
        import atexit
        from managers.payment_handler import cleanup_payment_handler
        atexit.register(cleanup_payment_handler)
        
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error during initialization: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()