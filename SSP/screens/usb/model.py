from PyQt5.QtCore import QObject, pyqtSignal, QThread
from managers.usb_file_manager import USBFileManager

class USBMonitorThread(QThread):
    usb_detected = pyqtSignal(str)
    usb_removed = pyqtSignal(str)

    def __init__(self, usb_manager):
        super().__init__()
        self.usb_manager = usb_manager # Needed to share USB manager instance with the object
        self.monitoring = True

    # Automatically called when thread is started
    def run(self):
        print("USBMonitorThread started")
        while self.monitoring:
            new_drives, removed_drives = self.usb_manager.check_for_new_drives()
            if new_drives and self.monitoring:  # Check monitoring state before emitting
                self.usb_detected.emit(new_drives[0])
            # Need in case usb has no pdf so they remove the drive and we need to detect it again
            if removed_drives and self.monitoring:  # Check monitoring state before emitting
                self.usb_removed.emit(removed_drives[0])
            
            # Optimized sleep - shorter intervals for faster detection
            for _ in range(10):  # 10 * 50ms = 500ms total (faster response)
                if not self.monitoring:
                    break
                self.msleep(50)

        print("USBMonitorThread finished")

    def stop_monitoring(self):
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
            
            # Wait for thread to finish (with timeout to prevent hanging)
            if not self.monitoring_thread.wait(2000):  # Wait up to 2 seconds
                print("USB monitoring thread did not stop within timeout")
                # Force terminate if it's still running
                if self.monitoring_thread.isRunning():
                    self.monitoring_thread.terminate()
                    self.monitoring_thread.wait(1000)  # Wait for termination
                 
            self.monitoring_thread = None
            print("USB monitoring stopped")

    def on_usb_detected(self, drive_path):
        print(f"USB drive detected: {drive_path}")
        self.handle_usb_scan_result([drive_path])
    
    def on_usb_removed(self, drive_path):
        # Suppress self-initiated eject removals
        if hasattr(self, 'usb_manager') and getattr(self.usb_manager, 'eject_in_progress', False):
            print(f"USB drive removal detected but eject_in_progress=True; suppressing message for {drive_path}")
            self.usb_manager.eject_in_progress = False
        else:
            print(f"USB drive removed: {drive_path}")
            self.status_changed.emit("USB drive removed.", 'success')
        self.start_usb_monitoring()
    
    # Called when new usb drives are detected
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
        
        pdf_files = self.usb_manager.scan_pdf_files(drive_path)
        
        if pdf_files:
            self.status_changed.emit(f"Success! Found {len(pdf_files)} PDF file(s).", 'success')
            self.pdf_files_found.emit(pdf_files) # Pass pdf to file browser thru controller
        else:
            self.status_changed.emit("No PDF files found on this drive.", 'warning')
    
    # Called when the usb screen is entered and we want to start a new session
    def reset_usb_manager_state(self):
        # Reset USB manager's known drives cache
        self.usb_manager.last_known_drives = set()
        # Reset USB manager's session data
        self.usb_manager.files_in_use.clear()
        # Reset USB manager's operation in progress flag
        self.usb_manager.operation_in_progress = False
        # Reset USB manager's current usb drive
        self.usb_manager.current_usb_drive = None
        # Clean up old temporary directories to prevent memory leaks
        self.usb_manager.cleanup_all_temp_folders()

        print("USB manager state reset complete")
            
    # Final cleanup before leaving the usb screen
    def force_cleanup(self):
        self.stop_usb_monitoring()
        
        # Force cleanup all resources
        self.usb_manager.cleanup_all_resources()
            
    # Called in usb controller timeout
    def stop_all_operations(self):
        self.stop_usb_monitoring()

        self.usb_manager.stop_all_operations()

        print("All USB operations stopped")

