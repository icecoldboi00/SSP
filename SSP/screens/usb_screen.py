# usb_screen.py

import sys
import os
import shutil
import tempfile
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSpacerItem, QSizePolicy, QDialog, QMessageBox, QListWidget, QStackedLayout
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QColor
import threading

try:
    from screens.usb_file_manager import USBFileManager
    print("✅ USBFileManager imported successfully in usb_screen.py")
except Exception as e:
    print(f"❌ Failed to import USBFileManager in usb_screen.py: {e}")
    # Dummy fallback for development/testing
    class USBFileManager:
        def __init__(self):
            self.destination_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem", "DummySession")
            self.supported_extensions = ['.pdf']
            self.last_known_drives = set()
            os.makedirs(self.destination_dir, exist_ok=True)
            print(f"❗️ Using dummy USBFileManager. Destination: {self.destination_dir}")

        def get_usb_drives(self): return []
        def check_for_new_drives(self): return [], []
        def scan_and_copy_pdf_files(self, source_dir): return []
        def cleanup_temp_files(self): pass
        def cleanup_all_temp_folders(self): pass
        def get_temp_folder_info(self): return None
        def get_drive_info(self, drive_path): return None

def get_base_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class USBMonitorThread(QThread):
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
                if new_drives: self.usb_detected.emit(new_drives[0])
                elif removed_drives: self.usb_removed.emit(removed_drives[0])
                self.msleep(2000)
            except Exception as e:
                print(f"Error monitoring USB: {e}")
                self.msleep(2000)

    def stop_monitoring(self):
        self.monitoring = False

class USBScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.usb_manager = USBFileManager()
        self.monitoring_thread = None
        self.STATUS_COLORS = {
            'monitoring': '#ff9900',
            'success': '#33ff33',
            'warning': '#ff9900',
            'error': '#ff3333'
        }
        self.STATUS_Y_POS = 410
        self.STATUS_HEIGHT = 50
        
        self.setup_ui()
        self.setup_timers()
        try:
            self.usb_manager.cleanup_all_temp_folders()
        except Exception as e:
            print(f"Error cleaning up old temp folders: {e}")

    def setup_ui(self):
        SCREEN_WIDTH = 1200
        SCREEN_HEIGHT = 800
        
        self.background_label = QLabel(self)
        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'usb_screen background.png')
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.background_label.setPixmap(pixmap)
            self.background_label.setScaledContents(True)
        self.background_label.setGeometry(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT)

        title = QLabel("INSERT USB FLASHDRIVE", self)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #36454F; font-size: 42px; font-weight: bold;")
        title.setGeometry((SCREEN_WIDTH - 800) // 2, 150, 800, 60)

        instruction = QLabel("Please insert your flash drive into the USB port below. The system will automatically check for the drive.", self)
        instruction.setAlignment(Qt.AlignCenter)
        instruction.setWordWrap(True)
        instruction.setStyleSheet("color: #36454F; font-size: 28px; line-height: 1.4;")
        instruction.setGeometry((SCREEN_WIDTH - 900) // 2, 230, 900, 100)

        nfd_label = QLabel("No flash drive found? Click the manual scan button.", self)
        nfd_label.setAlignment(Qt.AlignCenter)
        nfd_label.setWordWrap(True)
        nfd_label.setStyleSheet("color: #36454F; font-size: 18px; font-style: italic;")
        nfd_label.setGeometry((SCREEN_WIDTH - 600) // 2, 350, 600, 30)

        self.status_indicator = QLabel("...", self)
        self.status_indicator.setAlignment(Qt.AlignCenter)

        button_width, button_height, button_y = 200, 50, 490
        button_spacing = 30
        total_button_width = (button_width * 3) + (button_spacing * 2)
        start_x = (SCREEN_WIDTH - total_button_width) // 2

        scan_button = QPushButton("Manual Scan", self)
        scan_button.setGeometry(start_x, button_y, button_width, button_height)
        scan_button.clicked.connect(self.manual_scan_usb_drives)
        
        test_button = QPushButton("TEST: Simulate PDF", self)
        test_button.setGeometry(start_x + button_width + button_spacing, button_y, button_width, button_height)
        test_button.clicked.connect(self.test_simulate_files_found)
        
        clean_button = QPushButton("Clean Temp Files", self)
        clean_button.setGeometry(start_x + (button_width + button_spacing) * 2, button_y, button_width, button_height)
        clean_button.clicked.connect(self.manual_cleanup)
        
        button_style = """
            QPushButton { background-color: #1e440a; color: white; font-size: 18px;
                font-weight: bold; border: none; border-radius: 8px; }
            QPushButton:hover { background-color: #2a5d1a; }
            QPushButton:pressed { background-color: #142e07; } """
        scan_button.setStyleSheet(button_style)
        test_button.setStyleSheet(button_style)
        clean_button.setStyleSheet(button_style)
        
        back_button = QPushButton("← Back to Idle", self)
        back_button.setGeometry(50, SCREEN_HEIGHT - 90, 180, 40)
        back_button.setStyleSheet("""
            QPushButton { background-color: #1e440a; color: white; font-size: 18px;
                border: none; border-radius: 6px; padding: 10px 20px; }
            QPushButton:hover { background-color: #2a5d1a; } """)
        back_button.clicked.connect(self.go_back)

        cancel_button = QPushButton("Cancel", self)
        cancel_button.setGeometry(SCREEN_WIDTH - 50 - 120, SCREEN_HEIGHT - 90, 120, 40)
        cancel_button.setStyleSheet("""
            QPushButton { background-color: #FF0000; color: white; font-size: 18px;
                border: none; border-radius: 6px; padding: 10px 20px; }
            QPushButton:hover { background-color: #CC0000; } """)
        cancel_button.clicked.connect(self.cancel_operation)

    def _update_status_indicator(self, text, style_key):
        color_hex = self.STATUS_COLORS.get(style_key, '#ffffff')
        self.status_indicator.setText(text)
        color_rgb = QColor(color_hex).getRgb()
        self.status_indicator.setStyleSheet(f"""
            QLabel {{
                color: {color_hex}; font-size: 20px; padding: 10px;
                border: 2px solid {color_hex}; border-radius: 8px;
                background-color: rgba({color_rgb[0]}, {color_rgb[1]}, {color_rgb[2]}, 0.1);
            }} """)
        self.status_indicator.adjustSize()
        new_width = self.status_indicator.width()
        new_x = (self.width() - new_width) // 2
        self.status_indicator.setGeometry(new_x, self.STATUS_Y_POS, new_width, self.STATUS_HEIGHT)

    def blink_status(self):
        current_style = self.status_indicator.styleSheet()
        if "0.1" in current_style: new_style = current_style.replace("0.1", "0.05")
        else: new_style = current_style.replace("0.05", "0.1")
        self.status_indicator.setStyleSheet(new_style)

    # --- MODIFICATION START: The on_enter logic is completely replaced ---
    def on_enter(self):
        """
        On entering the screen, first check for existing drives.
        If a drive is found, process it immediately.
        If not, start the background monitor to wait for an insertion.
        """
        print("🔄 Entering USB screen, performing initial check...")
        self.blink_timer.start(1000)

        try:
            current_drives = self.usb_manager.get_usb_drives()
            print(f"Initial check found {len(current_drives)} drive(s): {current_drives}")

            if current_drives:
                if len(current_drives) == 1:
                    drive_path = current_drives[0]
                    self._update_status_indicator(f"USB drive found: {drive_path}", 'success')
                    # Use a short timer to allow the UI to update before processing
                    QTimer.singleShot(100, lambda: self.auto_process_drive(drive_path))
                else:
                    self._update_status_indicator("Multiple USB drives found. Please select one.", 'monitoring')
                    self.show_usb_selection_dialog(current_drives)
            else:
                # Only start monitoring if no drives are present initially
                print("No drives found initially. Starting background monitoring.")
                self.start_usb_monitoring()
        except Exception as e:
            print(f"Error during initial USB check: {e}")
            self._update_status_indicator("Error checking for USB drives.", 'error')
            self.start_usb_monitoring() # Fallback to monitoring
    # --- MODIFICATION END ---

    def on_leave(self):
        print("⏹️ Leaving USB screen")
        self.stop_usb_monitoring()
        self.blink_timer.stop()

    def start_usb_monitoring(self):
        if not self.monitoring_thread or not self.monitoring_thread.isRunning():
            self._update_status_indicator("Monitoring for USB devices...", 'monitoring')
            self.monitoring_thread = USBMonitorThread(self.usb_manager)
            self.monitoring_thread.usb_detected.connect(self.on_usb_detected)
            self.monitoring_thread.usb_removed.connect(self.on_usb_removed)
            self.monitoring_thread.start()

    def on_usb_detected(self, drive_path):
        self._update_status_indicator(f"USB drive detected: {drive_path}", 'success')
        QTimer.singleShot(100, lambda: self.auto_process_drive(drive_path))

    def on_usb_removed(self, drive_path):
        print(f"🔌 USB drive removed: {drive_path}")
        self._update_status_indicator("USB drive removed. Insert drive to continue.", 'error')

    def auto_process_drive(self, drive_path):
        self.stop_usb_monitoring()
        pdf_files = self.usb_manager.scan_and_copy_pdf_files(drive_path)
        if pdf_files:
            self._update_status_indicator(f"Found {len(pdf_files)} PDF files! Loading...", 'success')
            self.processing_complete(pdf_files, None)
        else:
            self._update_status_indicator("No PDF files found on USB drive.", 'error')
            self.start_usb_monitoring()

    def handle_usb_scan_result(self, usb_drives):
        if usb_drives:
            self._update_status_indicator(f"Found {len(usb_drives)} USB drive(s)!", 'success')
            if len(usb_drives) == 1:
                QTimer.singleShot(100, lambda: self.auto_process_drive(usb_drives[0]))
            else:
                self.show_usb_selection_dialog(usb_drives)
        else:
            self._update_status_indicator("No USB drives detected. Please insert USB drive.", 'warning')
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.background_label.setGeometry(0, 0, self.width(), self.height())
    
    def test_simulate_files_found(self):
        print("\n=== TEST: Simulating PDF files found ===")
        temp_storage_dir = self.usb_manager.destination_dir
        os.makedirs(temp_storage_dir, exist_ok=True)
        dummy_pdf_files_data = []
        dummy_filenames = ["simulated_document_1.pdf", "simulated_report_2.pdf", "another_sim_pdf_3.pdf"]
        for i, filename in enumerate(dummy_filenames):
            dummy_path = os.path.join(temp_storage_dir, filename)
            try:
                with open(dummy_path, 'wb') as f: f.write(b"%PDF-1.4\n1 0 obj<</Type/Page>>endobj\nxref\n0 2\n0000000000 65535 f \n0000000009 00000 n \ntrailer<</Size 2/Root 1 0 R>>\nstartxref\n24\n%%EOF")
                pdf_info = { 'filename': filename, 'size': os.path.getsize(dummy_path), 'pages': i + 3, 'path': dummy_path, 'type': '.pdf' }
                dummy_pdf_files_data.append(pdf_info)
            except Exception as e: print(f"Error creating dummy file {dummy_path}: {e}")
        if not dummy_pdf_files_data:
            QMessageBox.warning(self, "Test Warning", "Failed to create dummy PDF files for simulation.")
            return
        self.processing_complete(dummy_pdf_files_data, None)

    def setup_timers(self):
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.blink_status)
        self.blink_state = True

    def stop_usb_monitoring(self):
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop_monitoring()
            self.monitoring_thread.wait()
            print("✅ USB monitoring stopped")

    def processing_complete(self, pdf_files, dialog):
        if pdf_files:
            self.main_app.file_browser_screen.load_pdf_files(pdf_files)
            self.main_app.show_screen('file_browser')
        else:
            self._update_status_indicator("No PDF files found on USB drive", 'error')
            self.start_usb_monitoring()

    def processing_error(self, error_message, dialog):
        if dialog: dialog.accept()
        self._update_status_indicator(f"Error: {error_message}", 'error')
        self.start_usb_monitoring()

    def manual_scan_usb_drives(self):
        self._update_status_indicator("Scanning for USB drives...", 'monitoring')
        def scan_thread():
            usb_drives = self.usb_manager.get_usb_drives()
            QTimer.singleShot(0, lambda: self.handle_usb_scan_result(usb_drives))
        threading.Thread(target=scan_thread, daemon=True).start()

    def show_usb_selection_dialog(self, usb_drives):
        dialog = QDialog(self)
        dialog.setWindowTitle("USB Drive Selection")
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        dialog.exec_()

    def manual_cleanup(self):
        reply = QMessageBox.question(self, 'Clean Temporary Files', 'Are you sure?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes: self.usb_manager.cleanup_temp_files()

    def go_back(self):
        self.main_app.show_screen('idle')

    def cancel_operation(self):
        self.main_app.show_screen('idle')