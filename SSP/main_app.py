# main_app.py

import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from screens.idle_screen import IdleScreen
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

        # Create all screen instances once in the correct order
        self.idle_screen = IdleScreen(self)
        self.usb_screen = USBScreen(self)
        self.file_browser_screen = FileBrowserScreen(self)
        self.printing_options_screen = Print_Options_Screen(self)
        self.payment_screen = PaymentScreen(self)

        # Add screens to the stack in the same order
        self.stacked_widget.addWidget(self.idle_screen)         # Index 0
        self.stacked_widget.addWidget(self.usb_screen)          # Index 1
        self.stacked_widget.addWidget(self.file_browser_screen) # Index 2
        self.stacked_widget.addWidget(self.printing_options_screen) # Index 3
        self.stacked_widget.addWidget(self.payment_screen)      # Index 4

        ## FIX: Updated the print statement to be accurate.
        print(f"Stacked widget has {self.stacked_widget.count()} screens")
        print(f"Screen index map: idle=0, usb=1, file_browser=2, printing_options=3, payment=4")

        ## FIX: Set the initial screen to 'idle'.
        self.show_screen('idle')

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
        """)
        print("Main app initialization complete")

    def show_screen(self, screen_name):
        """Switch between screens using a predefined map."""
        print(f"\n🔄 Attempting to show screen: {screen_name}")

        ## FIX: The screen map is now correct and matches the widget order.
        screen_map = {
            'idle': 0,
            'usb': 1,
            'file_browser': 2,
            'printing_options': 3,
            'payment': 4
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