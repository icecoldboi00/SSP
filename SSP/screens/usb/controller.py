from PyQt5.QtWidgets import QWidget, QGridLayout
from PyQt5.QtCore import QTimer

from .model import USBScreenModel
from .view import USBScreenView

class USBController(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        
        self.model = USBScreenModel()
        self.view = USBScreenView()
        
        # 3 (on enter) or 5 (on click) min timeout back to idle 
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True) # Fire once only
        self.timeout_timer.timeout.connect(self._on_timeout)
        
        # 3 sec timeout for stuck operations 
        self.operation_timeout = QTimer()
        self.operation_timeout.setSingleShot(True)
        self.operation_timeout.timeout.connect(self._on_operation_timeout)
        
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, 0, 0)
        
        self._connect_signals()
    
    def _connect_signals(self):
        self.view.back_button_clicked.connect(self._go_back)
        self.view.back_button_clicked.connect(self._reset_timeout)
        
        self.model.status_changed.connect(self._update_status)
        self.model.usb_detected.connect(self.model.on_usb_detected)
        self.model.usb_removed.connect(self.model.on_usb_removed)
        self.model.pdf_files_found.connect(self._handle_pdf_files_found)
        self.model.show_message.connect(self.view.show_message)
    
    def _update_status(self, text, style_key):
        color_hex = self.model.get_status_color(style_key)
        self.view.update_status_indicator(text, style_key, color_hex)
    
    # Pass list[dict] to file browser screen
    def _handle_pdf_files_found(self, pdf_files):
        self.main_app.file_browser_screen.load_pdf_files(pdf_files) # Pass pdf file to  file browser screen
        self.main_app.show_screen('file_browser')
    
    def _go_back(self):
        self.main_app.show_screen('idle')
    
    def on_enter(self):
        try:
            self.view.start_blinking()
            
            # Removes any remaining files from the previous session. New session
            self.model.reset_usb_manager_state()
            print("Cleaned up previous session")
            
            # Start timeout timer (3 minutes) - reduced for faster exit
            self.timeout_timer.start(180000)
            print("USB screen timeout started 3 minutes")
            
            # Start operation timeout (30 seconds) - much shorter for stability
            self.operation_timeout.start(30000)
            print("USB operation timeout started 30 seconds")
            
            # Start monitoring in background - no immediate heavy operations
            self.model.start_usb_monitoring()
        except Exception as e:
            print(f"Error entering USB screen: {e}")
            self.main_app.show_screen('idle')

    
    def on_leave(self):
        try:
            print("Leaving USB screen")
            self.model.stop_usb_monitoring()
            self.view.stop_blinking()
            
            # Stop timeout timer
            self.timeout_timer.stop()
            
            # Force cleanup of any remaining resources
            self.model.force_cleanup()
        except Exception as e:
            print(f"Error leaving USB screen: {e}")
        

    def _on_timeout(self):
        # Safety check: Only navigate if we're still on this screen
        if self.main_app.stacked_widget.currentWidget() != self:
            print("USB timeout fired but we're not on this screen anymore - ignoring")
            return
        
        print("USB screen timeout - returning to idle screen")
        self.main_app.show_screen('idle')
    
    def _on_operation_timeout(self):
        print("USB operation timeout")
        # Only stop if operations are actually stuck, not just taking time
        if self.model.usb_manager and self.model.usb_manager.operation_in_progress:
            self.model.stop_all_operations()
        else:
            print("Ok!")
    
    def _reset_timeout(self):
        self.timeout_timer.stop()
        self.timeout_timer.start(300000)
        print("USB screen timeout reset")
