# main_app.py

import sys
import os
# This ensures that modules in subdirectories like 'printing' can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from screens.idle_screen import IdleScreen
from screens.usb_screen import USBScreen
from screens.file_browser_screen import FileBrowserScreen
from screens.payment_dialog import PaymentScreen
from screens.Print_Options_Screen import Print_Options_Screen
from screens.admin_screen import AdminScreen
from screens.thank_you_screen import ThankYouScreen
from database.models import init_db
from printing.printer_manager import PrinterManager  # Import the new manager
from sms_manager import cleanup_sms

try:
    from screens.usb_file_manager import USBFileManager
    print("✅ USBFileManager imported successfully in main_app.py")
except Exception as e:
    print(f"❌ Failed to import USBFileManager in main_app.py: {e}")

class PrintingSystemApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Printing System GUI")
        # --- MODIFICATION: Changed default window size ---
        self.setGeometry(100, 100, 1024, 600)
        self.setMinimumSize(1024, 600)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # --- Initialize Printer Manager ---
        print("Initializing printer manager...")
        self.printer_manager = PrinterManager()
        print("Printer manager initialized.")

        print("Initializing screens...")

        # Create all screen instances
        self.idle_screen = IdleScreen(self)
        self.usb_screen = USBScreen(self)
        self.file_browser_screen = FileBrowserScreen(self)
        self.printing_options_screen = Print_Options_Screen(self)
        self.payment_screen = PaymentScreen(self)
        self.admin_screen = AdminScreen(self)
        self.thank_you_screen = ThankYouScreen(self) # Initialize the new screen

        # Add screens to the stack
        self.stacked_widget.addWidget(self.idle_screen)         # Index 0
        self.stacked_widget.addWidget(self.usb_screen)          # Index 1
        self.stacked_widget.addWidget(self.file_browser_screen) # Index 2
        self.stacked_widget.addWidget(self.printing_options_screen) # Index 3
        self.stacked_widget.addWidget(self.payment_screen)      # Index 4
        self.stacked_widget.addWidget(self.admin_screen)        # Index 5
        self.stacked_widget.addWidget(self.thank_you_screen)    # Index 6

        ## FIX: Updated the print statement to be accurate.
        print(f"Stacked widget has {self.stacked_widget.count()} screens")
        print(f"Screen index map: idle=0, usb=1, file_browser=2, printing_options=3, payment=4, admin=5, thank_you=6")

        ## FIX: Set the initial screen to 'idle'.
        self.show_screen('idle')

        self.setStyleSheet("""
            QMainWindow {
                background-color: transparent;
            }
        """)
        print("Main app initialization complete")

        # Connect payment and printing signals
        self.payment_screen.payment_completed.connect(self.on_payment_completed)
        self.printer_manager.print_job_successful.connect(self.on_print_successful)
        self.printer_manager.print_job_failed.connect(self.on_print_failed)
        self.printer_manager.print_job_waiting.connect(self.on_print_waiting)

    def show_screen(self, screen_name):
        """Switch between screens, calling on_leave and on_enter methods."""
        print(f"\n🔄 Attempting to show screen: {screen_name}")

        ## FIX: The screen map is now correct and includes the admin and thank_you screens.
        screen_map = {
            'idle': 0,
            'usb': 1,
            'file_browser': 2,
            'printing_options': 3,
            'payment': 4,
            'admin': 5,
            'thank_you': 6
        }

        if screen_name in screen_map:
            # FIX: Call on_leave for the current screen
            current_widget = self.stacked_widget.currentWidget()
            if hasattr(current_widget, 'on_leave'):
                print(f"  -> Calling on_leave() for {type(current_widget).__name__}")
                current_widget.on_leave()

            # Switch to the new screen
            target_index = screen_map[screen_name]
            self.stacked_widget.setCurrentIndex(target_index)
            
            # FIX: Call on_enter for the new screen
            new_widget = self.stacked_widget.currentWidget()
            if hasattr(new_widget, 'on_enter'):
                print(f"  -> Calling on_enter() for {type(new_widget).__name__}")
                new_widget.on_enter()
            
            print(f"✅ Successfully switched to '{screen_name}' screen at index {target_index}")
        else:
            print(f"❌ ERROR: Unknown screen name: {screen_name}")

    def on_payment_completed(self, payment_info):
        """Handle successful payment and start the printing process."""
        print(f"Payment completed. Starting print job for {payment_info['pdf_data']['filename']}...")
        
        # The transition to the thank_you_screen is handled by the payment_dialog after
        # change is dispensed. We just need to kick off the printing here.
        self.printer_manager.print_file(
            file_path=payment_info['pdf_data']['path'],
            copies=payment_info['copies'],
            color_mode=payment_info['color_mode'],
            selected_pages=payment_info['selected_pages']
        )

    def on_print_successful(self):
        """Called when the print job is successfully completed."""
        print("✅ Print job successfully completed.")
        # Tell the thank you screen to update its state to 'finished'
        # Check if we are on the correct screen, as this signal is asynchronous
        if self.stacked_widget.currentWidget() == self.thank_you_screen:
            print("Thank you screen is active, calling finish_printing()")
            self.thank_you_screen.finish_printing()
        else:
            print(f"Warning: Print successful signal received, but not on thank you screen. Current screen: {type(self.stacked_widget.currentWidget()).__name__}")

    def on_print_waiting(self):
        """Called when the print job is sent and we're waiting for actual printing to complete."""
        print("⏳ Waiting for print job to complete...")
        # Tell the thank you screen to show waiting status
        if self.stacked_widget.currentWidget() == self.thank_you_screen:
            print("Thank you screen is active, showing waiting status")
            self.thank_you_screen.show_waiting_for_print()
        else:
            print(f"Warning: Print waiting signal received, but not on thank you screen. Current screen: {type(self.stacked_widget.currentWidget()).__name__}")

    def on_print_failed(self, error_message):
        """Called when the print job fails."""
        print(f"❌ Print job failed: {error_message}")
        # Tell the thank you screen to show an error message
        if self.stacked_widget.currentWidget() == self.thank_you_screen:
            self.thank_you_screen.show_printing_error(error_message)
        else:
            print(f"Warning: Print failed signal received, but not on thank you screen. Error: {error_message}")

    def cleanup(self):
        """Clean up resources when the application is closing."""
        print("Cleaning up application resources...")
        try:
            cleanup_sms()
            print("SMS system cleaned up")
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def closeEvent(self, event):
        """Handle application close event."""
        self.cleanup()
        event.accept()

def main():
    try:
        print("\n🔄 Initializing database...")
        init_db()
        print("✅ Database initialization successful\n")
        
        # Start application
        app = QApplication(sys.argv)
        app.setApplicationName("Printing System GUI")
        app.setApplicationVersion("1.0")
        window = PrintingSystemApp()

        # --- MODIFICATION: Set to show normal window by default ---
        # For deployment, comment out window.show() and uncomment window.showFullScreen()
        # window.show()
        window.showFullScreen()
        
        sys.exit(app.exec_())
    except Exception as e:
        print(f"❌ Error during initialization: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()