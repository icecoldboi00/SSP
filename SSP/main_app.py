import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from screens.idle_screen import IdleScreen
from screens.usb_screen import USBScreen
from screens.file_browser_screen import FileBrowserScreen

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
        
        # Create stacked widget for screen management
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        print("Initializing screens...")
        
        # Create screens
        self.idle_screen = IdleScreen(self)
        print("✅ Idle screen created")
        
        self.usb_screen = USBScreen(self)
        print("✅ USB screen created")
        
        self.file_browser_screen = FileBrowserScreen(self)
        print("✅ File browser screen created")
        
        # Add screens to stack
        self.stacked_widget.addWidget(self.idle_screen)
        self.stacked_widget.addWidget(self.usb_screen)
        self.stacked_widget.addWidget(self.file_browser_screen)
        
        print(f"Stacked widget has {self.stacked_widget.count()} screens")
        
        # Set initial screen
        self.show_screen('idle')
        
        # Apply global stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
        """)
        
        print("Main app initialization complete")
    
    def show_screen(self, screen_name):
        """Switch between screens"""
        print(f"Attempting to show screen: {screen_name}")
        
        screen_map = {
            'idle': 0,
            'usb': 1,
            'file_browser': 2
        }
        
        if screen_name in screen_map:
            # Handle screen exit/enter events
            current_widget = self.stacked_widget.currentWidget()
            current_index = self.stacked_widget.currentIndex()
            
            print(f"Current screen index: {current_index}, switching to: {screen_map[screen_name]}")
            
            if hasattr(current_widget, 'on_leave'):
                current_widget.on_leave()
            
            self.stacked_widget.setCurrentIndex(screen_map[screen_name])
            
            new_widget = self.stacked_widget.currentWidget()
            print(f"New screen widget: {type(new_widget).__name__}")
            
            if hasattr(new_widget, 'on_enter'):
                new_widget.on_enter()
            
            print(f"Successfully switched to {screen_name} screen")
        else:
            print(f"ERROR: Unknown screen name: {screen_name}")

def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("Printing System GUI")
    app.setApplicationVersion("1.0")
    
    # Create and show main window
    window = PrintingSystemApp()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
