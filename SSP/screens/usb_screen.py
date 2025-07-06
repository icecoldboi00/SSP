import sys
import os # Added for dummy file creation
import shutil # Added for dummy file creation
import tempfile # Added for dummy file creation

from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QFrame, QSpacerItem, QSizePolicy,
                             QDialog, QProgressBar, QMessageBox, QListWidget)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont
import threading
try:
    from screens.usb_file_manager import USBFileManager
    print("✅ USBFileManager imported successfully in usb_screen.py")
except Exception as e:
    print(f"❌ Failed to import USBFileManager in usb_screen.py: {e}")
    # Create a dummy class as fallback
    class USBFileManager:
        def __init__(self):
            self.destination_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem", "DummySession") # Ensure a dummy temp dir
            self.supported_extensions = ['.pdf']
            self.last_known_drives = set()
            os.makedirs(self.destination_dir, exist_ok=True) # Ensure dummy dir exists
            print(f"❗️ Using dummy USBFileManager. Destination: {self.destination_dir}")

        def get_usb_drives(self): return []
        def check_for_new_drives(self): return [], []
        def scan_and_copy_pdf_files(self, source_dir): 
            # Return dummy data for testing
            # Create a simple dummy PDF in the dummy temp dir
            dummy_filename = "dummy_auto_detect.pdf"
            dummy_path = os.path.join(self.destination_dir, dummy_filename)
            try:
                with open(dummy_path, 'wb') as f:
                    f.write(b'%PDF-1.4\n1 0 obj<</Type/Page/Contents(Dummy)>>endobj\nxref\n0 2\n0000000000 00000 n\n0000000009 00000 n\ntrailer<</Size 2/Root 1 0 R>>startxref\n0\n%%EOF')
                print(f"Dummy PDF created for auto-detection: {dummy_path}")
            except Exception as e:
                print(f"Error creating dummy PDF for auto-detect: {e}")
                dummy_path = "" # If creation fails, path is invalid

            return [
                {
                    'filename': dummy_filename,
                    'size': 1024 * 500 if os.path.exists(dummy_path) else 0,
                    'pages': 3,
                    'path': dummy_path,
                    'type': '.pdf'
                }
            ] if os.path.exists(dummy_path) else [] # Only return if dummy created

        def cleanup_temp_files(self): 
            if os.path.exists(self.destination_dir):
                shutil.rmtree(self.destination_dir)
                os.makedirs(self.destination_dir, exist_ok=True) # Recreate empty dir
            print("Dummy cleanup_temp_files called.")

        def cleanup_all_temp_folders(self):
            temp_base_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem")
            if os.path.exists(temp_base_dir):
                shutil.rmtree(temp_base_dir)
            os.makedirs(temp_base_dir, exist_ok=True)
            print("Dummy cleanup_all_temp_folders called.")


        def estimate_pdf_pages(self, file_path): return 1
        def get_drive_info(self, drive_path):
            try:
                total, used, free = shutil.disk_usage(drive_path)
                total_gb = total // (1024**3)
                used_gb = used // (1024**3)
                free_gb = free // (1024**3)
                return {
                    'path': drive_path,
                    'total_gb': total_gb,
                    'used_gb': used_gb,
                    'free_gb': free_gb,
                    'is_removable': True,
                    'filesystem': "Unknown"
                }
            except Exception as e:
                print(f"Error getting drive info for {drive_path}: {e}")
                return None

class USBMonitorThread(QThread):
    """Thread for monitoring USB drives"""
    usb_detected = pyqtSignal(str)
    usb_removed = pyqtSignal(str)
    
    def __init__(self, usb_manager):
        super().__init__()
        self.usb_manager = usb_manager
        self.monitoring = False
    
    def run(self):
        self.monitoring = True
        while self.monitoring:
            try:
                new_drives, removed_drives = self.usb_manager.check_for_new_drives()
                
                if new_drives:
                    print(f"Detected new USB drives: {new_drives}")
                    self.usb_detected.emit(new_drives[0])
                elif removed_drives:
                    print(f"Detected removed USB drives: {removed_drives}")
                    self.usb_removed.emit(removed_drives[0])
                
                self.msleep(2000)  # Check every 2 seconds
            except Exception as e:
                print(f"Error monitoring USB: {e}")
                self.msleep(2000)
    
    def stop_monitoring(self):
        self.monitoring = False
        print("USB monitoring thread stopping...")


class USBScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.usb_manager = USBFileManager()
        self.monitoring_thread = None
        self.setup_ui()
        self.setup_timers()
        
        # Clean up old session folders on startup
        try:
            self.usb_manager.cleanup_all_temp_folders()
            print("Cleaned up old temporary session folders on startup.")
        except Exception as e:
            print(f"Error cleaning up old temp folders on startup: {e}")
    
    def setup_ui(self):
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create main frame with background
        main_frame = QFrame()
        main_frame.setStyleSheet("""
            QFrame {
                background-color: #262640;
                border: none;
            }
        """)
        
        frame_layout = QVBoxLayout(main_frame)
        frame_layout.setContentsMargins(50, 50, 50, 50)
        frame_layout.setSpacing(30)
        
        # Title
        title = QLabel("READY TO PRINT PDFs")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 42px;
                font-weight: bold;
                margin: 20px;
            }
        """)
        
        # USB icon (using text emoji)
        usb_icon = QLabel("🔌")
        usb_icon.setAlignment(Qt.AlignCenter)
        usb_icon.setStyleSheet("""
            QLabel {
                font-size: 80px;
                margin: 20px;
            }
        """)
        
        # Main instruction
        instruction = QLabel("Insert your USB drive with PDF files\nSystem will detect it automatically")
        instruction.setAlignment(Qt.AlignCenter)
        instruction.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 28px;
                line-height: 1.4;
                margin: 20px;
            }
        """)
        
        # Status indicator
        self.status_indicator = QLabel("Monitoring for USB devices...")
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self.status_indicator.setStyleSheet("""
            QLabel {
                color: #ffff33;
                font-size: 20px;
                margin: 15px;
                padding: 10px;
                border: 2px solid #ffff33;
                border-radius: 8px;
                background-color: rgba(255, 255, 51, 0.1);
            }
        """)
        
        # Temp folder info
        self.temp_info_label = QLabel("")
        self.temp_info_label.setAlignment(Qt.AlignCenter)
        self.temp_info_label.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 12px;
                margin: 5px;
            }
        """)
        self.update_temp_info()
        
        # Supported formats
        formats_label = QLabel("Supported format: PDF files only")
        formats_label.setAlignment(Qt.AlignCenter)
        formats_label.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 16px;
                margin: 10px;
            }
        """)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(20)
        
        # Manual scan button
        scan_button = QPushButton("Manual Scan")
        scan_button.setMinimumHeight(50)
        scan_button.setStyleSheet("""
            QPushButton {
                background-color: #33cc33;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #28a428;
            }
            QPushButton:pressed {
                background-color: #1e7e1e;
            }
        """)
        scan_button.clicked.connect(self.manual_scan_usb_drives)
        
        # TEST BUTTON - Add a test button to simulate finding files
        test_button = QPushButton("TEST: Simulate PDF Files Found")
        test_button.setMinimumHeight(50)
        test_button.setStyleSheet("""
            QPushButton {
                background-color: #ff6600;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #e55a00;
            }
        """)
        test_button.clicked.connect(self.test_simulate_files_found)
        
        # Clean temp button
        clean_button = QPushButton("Clean Temp Files")
        clean_button.setMinimumHeight(50)
        clean_button.setStyleSheet("""
            QPushButton {
                background-color: #cc8033;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #dd9044;
            }
            QPushButton:pressed {
                background-color: #bb7022;
            }
        """)
        clean_button.clicked.connect(self.manual_cleanup)
        
        buttons_layout.addWidget(scan_button)
        buttons_layout.addWidget(test_button)  # Add test button
        buttons_layout.addWidget(clean_button)
        
        # Bottom buttons layout
        bottom_layout = QHBoxLayout()
        
        # Back button
        back_button = QPushButton("← Back to Idle")
        back_button.setMinimumHeight(40)
        back_button.setStyleSheet("""
            QPushButton {
                background-color: #4d4d80;
                color: white;
                font-size: 18px;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #5d5d90;
            }
        """)
        back_button.clicked.connect(self.go_back)
        
        # Cancel button
        cancel_button = QPushButton("Cancel")
        cancel_button.setMinimumHeight(40)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #cc4d4d;
                color: white;
                font-size: 18px;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #dc5d5d;
            }
        """)
        cancel_button.clicked.connect(self.cancel_operation)
        
        bottom_layout.addWidget(back_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(cancel_button)
        
        # Add all widgets to frame layout
        frame_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        frame_layout.addWidget(title)
        frame_layout.addWidget(usb_icon)
        frame_layout.addWidget(instruction)
        frame_layout.addWidget(self.status_indicator)
        frame_layout.addWidget(self.temp_info_label)
        frame_layout.addWidget(formats_label)
        frame_layout.addLayout(buttons_layout)
        frame_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        frame_layout.addLayout(bottom_layout)
        
        layout.addWidget(main_frame)
        self.setLayout(layout)
    
    def test_simulate_files_found(self):
        """TEST METHOD: Simulate finding PDF files by creating dummy files in temp directory."""
        print("\n=== TEST: Simulating PDF files found ===")
        
        # Ensure the destination directory exists for dummy files
        temp_storage_dir = self.usb_manager.destination_dir
        os.makedirs(temp_storage_dir, exist_ok=True)
        print(f"Ensured temporary storage directory exists: {temp_storage_dir}")

        dummy_pdf_files_data = []
        
        # Create minimal dummy PDF files in the actual session temp directory
        dummy_filenames = ["simulated_document_1.pdf", "simulated_report_2.pdf", "another_sim_pdf_3.pdf"]
        for i, filename in enumerate(dummy_filenames):
            dummy_path = os.path.join(temp_storage_dir, filename)
            try:
                # Create a minimal dummy PDF content (just a few bytes)
                # This is a very basic PDF structure, enough for PyMuPDF to open
                pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Page/Contents(Dummy PDF Content)>>endobj\nxref\n0 2\n0000000000 00000 n\n0000000009 00000 n\ntrailer<</Size 2/Root 1 0 R>>startxref\n0\n%%EOF"
                with open(dummy_path, 'wb') as f:
                    f.write(pdf_content)
                
                dummy_size = os.path.getsize(dummy_path)
                dummy_pages = i + 3 # Assign arbitrary pages for testing
                
                pdf_info = {
                    'filename': filename,
                    'size': dummy_size,
                    'pages': dummy_pages,
                    'path': dummy_path, # This path now actually exists
                    'type': '.pdf'
                }
                dummy_pdf_files_data.append(pdf_info)
                print(f"Created dummy file: {dummy_path}")
            except Exception as e:
                print(f"Error creating dummy file {dummy_path}: {e}")

        if not dummy_pdf_files_data:
            print("WARNING: No dummy PDF files were successfully created. Transition might not occur.")
            QMessageBox.warning(self, "Test Warning", "Failed to create dummy PDF files for simulation. Transition might not occur.")
            return

        print(f"Prepared dummy data for processing: {dummy_pdf_files_data}")
        
        # Call processing_complete directly with the created dummy files
        # This bypasses actual USB scanning/copying, directly testing the transition logic
        self.processing_complete(dummy_pdf_files_data, None)
    
    def update_temp_info(self):
        """Update temporary folder information display"""
        try:
            temp_info = self.usb_manager.get_temp_folder_info()
            if temp_info:
                size_mb = temp_info['total_size'] / (1024 * 1024)
                self.temp_info_label.setText(
                    f"Temp folder: {temp_info['file_count']} files, {size_mb:.1f} MB | Session: {temp_info['session_id']}"
                )
            else:
                self.temp_info_label.setText("Temp folder: Empty")
        except Exception as e:
            self.temp_info_label.setText(f"Temp folder: Error ({e})")
    
    def setup_timers(self):
        """Setup timers for blinking effect"""
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.blink_status)
        self.blink_state = True
        
        # Timer to update temp info periodically
        self.temp_info_timer = QTimer()
        self.temp_info_timer.timeout.connect(self.update_temp_info)
        self.temp_info_timer.start(5000)  # Update every 5 seconds
    
    def blink_status(self):
        """Animate status indicator"""
        if self.blink_state:
            self.status_indicator.setStyleSheet("""
                QLabel {
                    color: #ffff33;
                    font-size: 20px;
                    margin: 15px;
                    padding: 10px;
                    border: 2px solid #ffff33;
                    border-radius: 8px;
                    background-color: rgba(255, 255, 51, 0.1);
                }
            """)
        else:
            self.status_indicator.setStyleSheet("""
                QLabel {
                    color: #ffff33;
                    font-size: 20px;
                    margin: 15px;
                    padding: 10px;
                    border: 2px solid #ffff33;
                    border-radius: 8px;
                    background-color: rgba(255, 255, 51, 0.05);
                }
            """)
        self.blink_state = not self.blink_state
    
    def on_enter(self):
        """Start monitoring when entering screen"""
        print("USBScreen entered.")
        self.start_usb_monitoring()
        self.blink_timer.start(1000)
        self.update_temp_info()
        # Initialize known drives
        try:
            self.usb_manager.last_known_drives = set(self.usb_manager.get_usb_drives())
        except Exception as e:
            print(f"Error initializing last_known_drives: {e}")
    
    def on_leave(self):
        """Stop monitoring when leaving screen"""
        print("USBScreen left.")
        self.stop_usb_monitoring()
        self.blink_timer.stop()
    
    def start_usb_monitoring(self):
        """Start real-time USB monitoring"""
        if not self.monitoring_thread or not self.monitoring_thread.isRunning():
            self.monitoring_thread = USBMonitorThread(self.usb_manager)
            self.monitoring_thread.usb_detected.connect(self.on_usb_detected)
            self.monitoring_thread.usb_removed.connect(self.on_usb_removed)
            self.monitoring_thread.start()
            print("USB monitoring started.")
            self.status_indicator.setText("Monitoring for USB devices...")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    color: #ffff33;
                    font-size: 20px;
                    margin: 15px;
                    padding: 10px;
                    border: 2px solid #ffff33;
                    border-radius: 8px;
                    background-color: rgba(255, 255, 51, 0.1);
                }
            """)
    
    def stop_usb_monitoring(self):
        """Stop USB monitoring"""
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop_monitoring()
            self.monitoring_thread.wait()
            print("USB monitoring stopped.")
    
    def on_usb_detected(self, drive_path):
        """Handle USB drive detection"""
        print(f"USB drive detected: {drive_path}. Attempting to auto-process.")
        self.status_indicator.setText(f"USB drive detected: {drive_path}")
        self.status_indicator.setStyleSheet("""
            QLabel {
                color: #33ff33;
                font-size: 20px;
                margin: 15px;
                padding: 10px;
                border: 2px solid #33ff33;
                border-radius: 8px;
                background-color: rgba(51, 255, 51, 0.1);
            }
        """)
        
        # Automatically process the drive after 1 second
        QTimer.singleShot(1000, lambda: self.auto_process_drive(drive_path))
    
    def on_usb_removed(self, drive_path):
        """Handle USB drive removal"""
        print(f"USB drive removed: {drive_path}. Resuming monitoring.")
        self.status_indicator.setText("USB drive removed. Insert drive to continue.")
        self.status_indicator.setStyleSheet("""
            QLabel {
                color: #ff8033;
                font-size: 20px;
                margin: 15px;
                padding: 10px;
                border: 2px solid #ff8033;
                border-radius: 8px;
                background-color: rgba(255, 128, 51, 0.1);
            }
        """)
        # Re-start monitoring after removal
        self.start_usb_monitoring()
    
    def auto_process_drive(self, drive_path):
        """Automatically process detected USB drive - scan and copy files"""
        self.stop_usb_monitoring()
        print(f"Auto-processing USB drive: {drive_path}")
        self.status_indicator.setText(f"Copying PDF files from {drive_path}...")
        self.status_indicator.setStyleSheet("""
            QLabel {
                color: #33ff33;
                font-size: 20px;
                margin: 15px;
                padding: 10px;
                border: 2px solid #33ff33;
                border-radius: 8px;
                background-color: rgba(51, 255, 51, 0.1);
            }
        """)
        
        # Scan and copy in background thread
        def scan_and_copy():
            try:
                print(f"Starting scan_and_copy_pdf_files for {drive_path}")
                pdf_files = self.usb_manager.scan_and_copy_pdf_files(drive_path)
                print(f"Scan and copy finished. Found {len(pdf_files)} files.")
                QTimer.singleShot(0, lambda: self.processing_complete(pdf_files, None))
            except Exception as e:
                print(f"Error during scan_and_copy: {e}")
                QTimer.singleShot(0, lambda: self.processing_error(str(e), None))
        
        threading.Thread(target=scan_and_copy, daemon=True).start()
    
    def manual_scan_usb_drives(self):
        """Manual scan for USB drives"""
        print("Manual USB scan initiated.")
        self.status_indicator.setText("Scanning for USB drives...")
        self.status_indicator.setStyleSheet("""
            QLabel {
                color: #ffff33;
                font-size: 20px;
                margin: 15px;
                padding: 10px;
                border: 2px solid #ffff33;
                border-radius: 8px;
                background-color: rgba(255, 255, 51, 0.1);
            }
        """)
        
        def scan_thread():
            print("Running USB scan in background thread.")
            usb_drives = self.usb_manager.get_usb_drives()
            print(f"Manual scan found drives: {usb_drives}")
            QTimer.singleShot(0, lambda: self.handle_usb_scan_result(usb_drives))
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def manual_cleanup(self):
        """Manually clean up temporary files"""
        reply = QMessageBox.question(self, 'Clean Temporary Files', 
                                   'This will delete all copied PDF files from the temporary folder.\n\nAre you sure?',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                self.usb_manager.cleanup_temp_files()
                self.update_temp_info()
                QMessageBox.information(self, "Cleanup Complete", "Temporary files have been deleted.")
                print("Manual temporary files cleanup completed.")
            except Exception as e:
                QMessageBox.warning(self, "Cleanup Error", f"Error during cleanup: {e}")
                print(f"Manual temporary files cleanup failed: {e}")
    
    def handle_usb_scan_result(self, usb_drives):
        """Handle the result of USB drive scan"""
        if usb_drives:
            self.status_indicator.setText(f"Found {len(usb_drives)} USB drive(s)!")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    color: #33ff33;
                    font-size: 20px;
                    margin: 15px;
                    padding: 10px;
                    border: 2px solid #33ff33;
                    border-radius: 8px;
                    background-color: rgba(51, 255, 51, 0.1);
                }
            """)
            
            if len(usb_drives) == 1:
                # Auto-process single drive
                print(f"Single USB drive found: {usb_drives[0]}. Auto-processing.")
                QTimer.singleShot(1000, lambda: self.auto_process_drive(usb_drives[0]))
            else:
                # Show selection dialog for multiple drives
                print(f"Multiple USB drives found: {usb_drives}. Showing selection dialog.")
                self.show_usb_selection_dialog(usb_drives)
        else:
            self.status_indicator.setText("No USB drives detected. Please insert USB drive.")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    color: #ff8033;
                    font-size: 20px;
                    margin: 15px;
                    padding: 10px;
                    border: 2px solid #ff8033;
                    border-radius: 8px;
                    background-color: rgba(255, 128, 51, 0.1);
                }
            """)
            print("No USB drives detected during manual scan.")
    
    def show_usb_selection_dialog(self, usb_drives):
        """Show dialog to select USB drive with detailed information"""
        dialog = QDialog(self)
        dialog.setWindowTitle("USB Drive Selection")
        dialog.setModal(True)
        dialog.setFixedSize(600, 400)
        dialog.setStyleSheet("QDialog { background-color: #2b2b2b; }")
        
        layout = QVBoxLayout()
        
        header = QLabel("Multiple USB drives detected. Select one:")
        header.setStyleSheet("color: white; font-size: 16px; margin: 10px; font-weight: bold;")
        layout.addWidget(header)
        
        # USB drive list with detailed info
        drive_list = QListWidget()
        drive_list.setStyleSheet("""
            QListWidget {
                background-color: #333;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #444;
            }
            QListWidget::item:selected {
                background-color: #4CAF50;
            }
            QListWidget::item:hover {
                background-color: #404040;
            }
        """)
        
        for drive in usb_drives:
            try:
                drive_info = self.usb_manager.get_drive_info(drive)
                if drive_info:
                    display_text = (f"🔌 {drive_info['path']}\n"
                                  f"   💾 {drive_info['filesystem']} | "
                                  f"📊 {drive_info['free_gb']:.1f}GB free / {drive_info['total_gb']:.1f}GB total\n"
                                  f"   📁 {drive_info['used_gb']:.1f}GB used")
                    
                    if drive_info['is_removable']:
                        display_text += " ✅ USB Drive"
                    else:
                        display_text += " ⚠️ May not be USB"
                else:
                    display_text = f"🔌 {drive}\n   ❌ Drive info unavailable"
                    
                drive_list.addItem(display_text)
            except Exception as e:
                drive_list.addItem(f"🔌 {drive}\n   ❌ Error: {str(e)}")
        
        layout.addWidget(drive_list)
        
        # Info label
        info_label = QLabel("💡 Only actual USB/removable drives are shown")
        info_label.setStyleSheet("color: #888; font-size: 12px; margin: 5px; font-style: italic;")
        layout.addWidget(info_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #666;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #777;
            }
        """)
        
        select_button = QPushButton("✅ Select Drive")
        select_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        cancel_button = QPushButton("❌ Cancel")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #d32f2f;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #f44336;
            }
        """)
        
        def on_refresh():
            dialog.accept()
            # Trigger a new scan
            QTimer.singleShot(100, self.manual_scan_usb_drives)
        
        def on_select():
            current_row = drive_list.currentRow()
            if current_row >= 0:
                selected_drive = usb_drives[current_row]
                dialog.accept()
                self.auto_process_drive(selected_drive)
            else:
                QMessageBox.warning(dialog, "No Selection", "Please select a USB drive first.")
        
        refresh_btn.clicked.connect(on_refresh)
        select_button.clicked.connect(on_select)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addWidget(refresh_btn)
        button_layout.addStretch()
        button_layout.addWidget(select_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        
        dialog.setLayout(layout)
        dialog.exec_()
    
    def processing_complete(self, pdf_files, dialog):
        """Handle completion of PDF file processing"""
        print(f"\n=== PROCESSING_COMPLETE CALLED ===")
        print(f"PDF files received: {pdf_files}")
        print(f"Number of files: {len(pdf_files) if pdf_files else 0}")
        
        if dialog:
            dialog.accept()
    
        if pdf_files:
            print(f"✅ Files found, updating status...")
            self.status_indicator.setText(f"Copied {len(pdf_files)} PDF files! Loading preview...")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    color: #4CAF50;
                    font-size: 20px;
                    margin: 15px;
                    padding: 10px;
                    border: 2px solid #4CAF50;
                    border-radius: 8px;
                    background-color: rgba(76, 175, 80, 0.1);
                }
            """)
        
            # Update temp info
            self.update_temp_info()
        
            print(f"Files details: {[f['filename'] for f in pdf_files]}")
        
            # Check if main_app exists and has file_browser_screen
            print(f"main_app type: {type(self.main_app)}")
            print(f"main_app has file_browser_screen: {hasattr(self.main_app, 'file_browser_screen')}")
            
            if hasattr(self.main_app, 'file_browser_screen'):
                print("✅ File browser screen exists")
                print(f"File browser screen type: {type(self.main_app.file_browser_screen)}")
                
                try:
                    print("Calling load_pdf_files...")
                    self.main_app.file_browser_screen.load_pdf_files(pdf_files)
                    print("✅ load_pdf_files completed successfully")
                    
                    print("Calling show_screen('file_browser')...")
                    self.main_app.show_screen('file_browser')
                    print("✅ show_screen completed successfully")
                    
                except Exception as e:
                    print(f"❌ Error during file browser transition: {e}")
                    import traceback
                    traceback.print_exc()
                    
                    # Show error message
                    QMessageBox.critical(self, "Transition Error", 
                                       f"Failed to transition to file browser:\n{str(e)}")
            else:
                print("❌ file_browser_screen not found in main_app!")
                print(f"main_app attributes: {dir(self.main_app)}")
                QMessageBox.critical(self, "Error", "File browser screen not initialized!")
        else:
            print("❌ No PDF files found")
            self.status_indicator.setText("No PDF files found on USB drive.")
            self.status_indicator.setStyleSheet("""
                QLabel {
                    color: #ff8033;
                    font-size: 20px;
                    margin: 15px;
                    padding: 10px;
                    border: 2px solid #ff8033;
                    border-radius: 8px;
                    background-color: rgba(255, 128, 51, 0.1);
                }
            """)
            # Restart monitoring
            self.start_usb_monitoring()
    
    def processing_error(self, error_message, dialog):
        """Handle processing error"""
        print(f"❌ Processing error: {error_message}")
        
        if dialog:
            dialog.accept()
        
        self.status_indicator.setText(f"Error: {error_message}")
        self.status_indicator.setStyleSheet("""
            QLabel {
                color: #ff3333;
                font-size: 20px;
                margin: 15px;
                padding: 10px;
                border: 2px solid #ff3333;
                border-radius: 8px;
                background-color: rgba(255, 51, 51, 0.1);
            }
        """)
        # Restart monitoring
        self.start_usb_monitoring()
    
    def cancel_processing(self):
        """Cancel PDF file processing"""
        print("Processing cancelled.")
        self.status_indicator.setText("Processing cancelled.")
        self.status_indicator.setStyleSheet("""
            QLabel {
                color: #ff8033;
                font-size: 20px;
                margin: 15px;
                padding: 10px;
                border: 2px solid #ff8033;
                border-radius: 8px;
                background-color: rgba(255, 128, 51, 0.1);
            }
        """)
        # Restart monitoring
        self.start_usb_monitoring()
    
    def go_back(self):
        """Go back to idle screen"""
        print("Going back to idle screen.")
        self.main_app.show_screen('idle')
    
    def cancel_operation(self):
        """Cancel operation with confirmation"""
        reply = QMessageBox.question(self, 'Cancel Operation', 
                                   'Are you sure you want to cancel?',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            print("Operation cancelled by user. Returning to idle screen.")
            self.main_app.show_screen('idle')