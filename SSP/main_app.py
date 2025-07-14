import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from screens.idle_screen import IdleScreen
from screens.usb_screen import USBScreen
from screens.file_browser_screen import FileBrowserScreen
from screens.admin_screen import AdminScreen

try:
    from screens.usb_file_manager import USBFileManager
    print("USBFileManager imported successfully in main_app.py")
except Exception as e:
    print(f"Failed to import USBFileManager in main_app.py: {e}")

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
        print("Idle screen created")
        
        self.usb_screen = USBScreen(self)
        print("USB screen created")
        
        self.file_browser_screen = FileBrowserScreen(self)
        print("File browser screen created")

        self.admin_screen = AdminScreen(self)
        print("Admin screen created")
        
        # Add screens to stack
        self.stacked_widget.addWidget(self.idle_screen)
        self.stacked_widget.addWidget(self.usb_screen)
        self.stacked_widget.addWidget(self.file_browser_screen)
        self.stacked_widget.addWidget(self.admin_screen)
        
        print(f"Stacked widget has {self.stacked_widget.count()} screens")
        print(f"Screen index map: idle=0, usb=1, file_browser=2") # Added for clarity
        
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
        print("\n=== SCREEN TRANSITION DEBUG ===")
        print(f"Attempting to show screen: {screen_name}")
        
        screen_map = {
            'idle': 0,
            'usb': 1,
            'file_browser': 2,
            'admin': 3
        }
        
        if screen_name in screen_map:
            try:
                # Handle screen exit/enter events
                current_widget = self.stacked_widget.currentWidget()
                current_index = self.stacked_widget.currentIndex()
                target_index = screen_map[screen_name]
                
                print(f"Current: index={current_index}, widget={type(current_widget).__name__}")
                print(f"Target: index={target_index}, screen={screen_name}")
                
                if hasattr(current_widget, 'on_leave'):
                    print(f"Calling on_leave for {type(current_widget).__name__}")
                    current_widget.on_leave()
                
                # Force immediate screen switch
                print(f"Setting current index to {target_index}")
                self.stacked_widget.setCurrentIndex(target_index)
                
                new_widget = self.stacked_widget.currentWidget()
                actual_index = self.stacked_widget.currentIndex()
                print(f"New widget: {type(new_widget).__name__} at index {actual_index}")
                
                if hasattr(new_widget, 'on_enter'):
                    print(f"Calling on_enter for {type(new_widget).__name__}")
                    new_widget.on_enter()
                
                # Force immediate update
                print("Forcing UI update")
                self.stacked_widget.update()
                QApplication.processEvents()
                
                # Verify the switch
                final_widget = self.stacked_widget.currentWidget()
                final_index = self.stacked_widget.currentIndex()
                print(f"Final state: index={final_index}, widget={type(final_widget).__name__}")
                
                if final_index == target_index:
                    print(f"Successfully switched to {screen_name} screen")
                    return True
                else:
                    print(f"Screen switch verification failed!")
                    print(f"Expected index {target_index}, but got {final_index}")
                    return False
                
            except Exception as e:
                print(f"Error during screen transition: {str(e)}")
                import traceback
                traceback.print_exc()
                return False
        else:
            print(f"ERROR: Unknown screen name: {screen_name}")
            return False

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