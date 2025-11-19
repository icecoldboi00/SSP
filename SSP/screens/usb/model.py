from PyQt5.QtCore import QObject, pyqtSignal, QThread
from managers.usb_file_manager import USBFileManager

class USBMonitorThread(QThread):
    usb_detected = pyqtSignal(str)
    usb_removed = pyqtSignal(str)

    def __init__(self, usb_manager):
        super().__init__()
        self.usb_manager = usb_manager # Needed to share USB manager instance with the object
        self.monitoring = True

    def run(self):
        print("USBMonitorThread started")
        while self.monitoring:
            new_drives, removed_drives = self.usb_manager.check_for_new_drives()
            if new_drives and self.monitoring:  # Check monitoring state before emitting
                self.usb_detected.emit(new_drives[0])
            if removed_drives and self.monitoring:  # Check monitoring state before emitting
                self.usb_removed.emit(removed_drives[0])
            
            # Optimized sleep - shorter intervals for faster detection
            for _ in range(10):  # 10 * 50ms = 500ms total (faster response)
                if not self.monitoring:
                    break
                self.msleep(50)

        print("USBMonitorThread finished")

    def stop_monitoring(self):
        print("USBMonitorThread stop requested")
        self.monitoring = False

class USBScreenModel(QObject):
    status_changed = pyqtSignal(str, str)  # Emits status text and style key
    usb_detected = pyqtSignal(str)         # Emits USB drive path
    usb_removed = pyqtSignal(str)          # Emits removed USB drive path
    pdf_files_found = pyqtSignal(list)     # Emits list of PDF files
    show_message = pyqtSignal(str, str)    # Emits message title and text
    
    def __init__(self):
        super().__init__()
        self.usb_manager = USBFileManager()
        self.monitoring_thread = None
        
        self.STATUS_COLORS = {
            'monitoring': '#ff9900',  # Orange
            'success': '#28a745',     # Green
            'warning': '#ffc107',     # Yellow
            'error': '#dc3545'        # Red
        }

    def get_status_color(self, style_key):
        return self.STATUS_COLORS.get(style_key, '#ffffff')
    
    def start_usb_monitoring(self):
        self.stop_usb_monitoring() # Stop any existing thread
        
        self.status_changed.emit("Monitoring for USB devices...", 'monitoring')
        self.monitoring_thread = USBMonitorThread(self.usb_manager)
        self.monitoring_thread.usb_detected.connect(self.usb_detected.emit)
        self.monitoring_thread.usb_removed.connect(self.usb_removed.emit)
        self.monitoring_thread.start()
        print("USB monitoring started")
    
    def stop_usb_monitoring(self):
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            print("Stopping USB monitoring thread...")
            
            try:
                self.monitoring_thread.usb_detected.disconnect()
                self.monitoring_thread.usb_removed.disconnect()
            except TypeError:
                # Signals might not be connected, ignore
                pass
            
            # Stop the monitoring loop
            self.monitoring_thread.stop_monitoring()
            
            # Wait for thread to finish gracefully
            if not self.monitoring_thread.wait(5000):  # Increased wait time to 5 seconds
                print("Thread did not stop, terminator engaged...")
                # Try to force stop the monitoring loop first
                self.monitoring_thread.monitoring = False
                
                if not self.monitoring_thread.wait(2000):
                    print("Forcing thread termination...")
                    self.monitoring_thread.terminate()
                    self.monitoring_thread.wait(1000)
            
            self.monitoring_thread = None
            print("USB monitoring stopped")
    
    def check_current_drives(self):
        try:
            self.stop_usb_monitoring()
            
            # Reset the USB manager's known drives to force fresh detection
            if hasattr(self.usb_manager, 'last_known_drives'):
                self.usb_manager.last_known_drives = set()
                print("Cleared USB manager's known drives cache")
            
            current_drives = self.usb_manager.get_usb_drives()
            if current_drives:
                self.handle_usb_scan_result(current_drives)
            else:
                self.start_usb_monitoring()
        except Exception as e:
            self.status_changed.emit("Error checking for USB drives.", 'error')
            print(f"Error during USB check: {e}")
    
    
    def handle_usb_scan_result(self, usb_drives):
        if not usb_drives:
            self.status_changed.emit("No USB drives found. Please insert a drive.", 'warning')
            self.start_usb_monitoring()
            return

        self.stop_usb_monitoring()
        
        if len(usb_drives) > 1:
            self.status_changed.emit(f"Found {len(usb_drives)} drives. Please connect only one.", 'error')
            return

        drive_path = usb_drives[0]
        self.status_changed.emit(f"USB drive found! Scanning for PDF files...", 'success')
        self.scan_files_from_drive(drive_path)
    
    def scan_files_from_drive(self, drive_path):
        pdf_files = self.usb_manager.scan_pdf_files(drive_path)
        
        if pdf_files:
            self.status_changed.emit(f"Success! Found {len(pdf_files)} PDF file(s). USB is now safe to remove.", 'success')
            self.pdf_files_found.emit(pdf_files)
        else:
            self.status_changed.emit("No PDF files found on this drive.", 'warning')
    
    def on_usb_detected(self, drive_path):
        print(f"USB drive detected: {drive_path}")
        self.handle_usb_scan_result([drive_path])
    
    def on_usb_removed(self, drive_path):
        print(f"USB drive removed: {drive_path}")
        self.status_changed.emit("USB drive removed.", 'success')
        self.start_usb_monitoring()
    
    def reset_usb_state(self):
        self.stop_usb_monitoring()
        
        # Clear USB manager's cache
        if hasattr(self.usb_manager, 'last_known_drives'):
            self.usb_manager.last_known_drives = set()
            print("Cleared USB manager's known drives cache")
        
        # Reset status
        self.status_changed.emit("Ready for USB device", 'monitoring')
        
        print("USB state reset complete")
    
    def reset_usb_manager_state(self):
        try:
            if hasattr(self.usb_manager, 'last_known_drives'):
                self.usb_manager.last_known_drives = set()
                print("Cleared USB manager's known drives cache")
            
            # Reset USB manager's session data
            if hasattr(self.usb_manager, 'files_in_use'):
                self.usb_manager.files_in_use.clear()
            if hasattr(self.usb_manager, 'operation_in_progress'):
                self.usb_manager.operation_in_progress = False
            if hasattr(self.usb_manager, 'current_usb_drive'):
                self.usb_manager.current_usb_drive = None
            
            # Clean up old temporary directories to prevent memory leaks
            if hasattr(self.usb_manager, 'cleanup_all_temp_folders'):
                self.usb_manager.cleanup_all_temp_folders()
                print("Cleaned up old temporary directories")
            
            print("USB manager state reset complete")
            
        except Exception as e:
            try:
                from utils.error_logger import log_error
                log_error("USB Manager Reset Error", str(e), "usb_screen_model")
            except Exception as log_error:
                print(f"Failed to log error: {log_error}")
    
    def force_cleanup(self):
        try:
            self.stop_usb_monitoring()
            
            # Force cleanup USB manager
            if hasattr(self.usb_manager, 'force_safe_eject'):
                self.usb_manager.force_safe_eject()
            
            # Force cleanup all resources
            if hasattr(self.usb_manager, 'force_cleanup_all_resources'):
                self.usb_manager.force_cleanup_all_resources()
            
            print("Force cleanup completed")
            
        except Exception as e:
            try:
                from utils.error_logger import log_error
                log_error("USB Force Cleanup Error", str(e), "usb_screen_model")
            except Exception as log_error:
                print(f"Failed to log error: {log_error}")
    
    def stop_all_operations(self):
        try:
            print("Stopping all USB operations...")
            
            # Stop USB monitoring thread
            if hasattr(self, 'monitoring_thread') and self.monitoring_thread:
                self.monitoring_thread.stop_monitoring()
                print("USB monitoring thread stopped")
            
            # Stop any file operations
            if hasattr(self, 'usb_manager') and self.usb_manager:
                self.usb_manager.stop_all_operations()
                print("USB file operations stopped")
            
        except Exception as e:
            print(f"Error stopping operations: {e}")
