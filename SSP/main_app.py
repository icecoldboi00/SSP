# main_app.py

import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from screens.usb_screen import USBScreen
from screens.file_browser_screen import FileBrowserScreen
from screens.payment_dialog import PaymentScreen
from screens.Print_Options_Screen import Print_Options_Screen

try:
    from screens.usb_file_manager import USBFileManager
    print("✅ USBFileManager imported successfully in main_app.py")
except Exception as e:
    print(f"❌ Failed to import USBFileManager in main_app.py: {e}")

class PrintingSystemApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Printing System GUI")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1000, 700)

        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        print("Initializing screens...")

        # Create all screen instances once
        # self.idle_screen = IdleScreen(self) # Commented out due to PinDialog error
        self.usb_screen = USBScreen(self)
        self.file_browser_screen = FileBrowserScreen(self)
        ## FIX: Instantiated the correctly named class 'Print_Options_Screen'
        self.printing_options_screen = Print_Options_Screen(self)
        self.payment_screen = PaymentScreen(self)

        # Add screens to the stack
        # self.stacked_widget.addWidget(self.idle_screen)
        self.stacked_widget.addWidget(self.usb_screen)
        self.stacked_widget.addWidget(self.file_browser_screen)
        self.stacked_widget.addWidget(self.printing_options_screen)
        self.stacked_widget.addWidget(self.payment_screen)

        ## FIX: Updated screen map to reflect the removal of idle_screen for now.
        ## You can add it back later.
        print(f"Stacked widget has {self.stacked_widget.count()} screens")
        print(f"Screen index map: usb=0, file_browser=1, printing_options=2, payment=3")

        # Set initial screen
        self.show_screen('usb') # Changed from 'idle' to 'usb' for testing

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
        """)
        print("Main app initialization complete")

    def show_screen(self, screen_name):
        """Switch between screens using a predefined map."""
        print(f"\n🔄 Attempting to show screen: {screen_name}")

        ## FIX: Updated map to match the current widget order.
        screen_map = {
            # 'idle': 0,
            'usb': 0,
            'file_browser': 1,
            'printing_options': 2,
            'payment': 3
        }

        if screen_name in screen_map:
            target_index = screen_map[screen_name]
            self.stacked_widget.setCurrentIndex(target_index)
            print(f"✅ Successfully switched to '{screen_name}' screen at index {target_index}")
        else:
            print(f"❌ ERROR: Unknown screen name: {screen_name}")

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Printing System GUI")
    app.setApplicationVersion("1.0")
    window = PrintingSystemApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()