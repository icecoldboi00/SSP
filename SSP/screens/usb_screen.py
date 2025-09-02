# usb_screen.py

import os
import sys
import tempfile
import threading
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedLayout,
    QMessageBox, QDialog
)

try:
    from screens.usb_file_manager import USBFileManager
    print("✅ USBFileManager imported successfully in usb_screen.py")
except ImportError:
    print("❌ Failed to import USBFileManager in usb_screen.py. Using fallback.")
    class USBFileManager:
        def __init__(self):
            self.destination_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem", "DummySession")
            os.makedirs(self.destination_dir, exist_ok=True)
            print(f"❗️ Using dummy USBFileManager. Destination: {self.destination_dir}")
        def get_usb_drives(self): return []
        def check_for_new_drives(self): return [], []
        def scan_and_copy_pdf_files(self, source_dir): return []
        def cleanup_all_temp_folders(self): pass
        def cleanup_temp_files(self): pass

def get_base_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class USBMonitorThread(QThread):
    usb_detected = pyqtSignal(str)
    usb_removed = pyqtSignal(str)

    def __init__(self, usb_manager):
        super().__init__()
        self.usb_manager = usb_manager
        self.monitoring = True

    def run(self):
        while self.monitoring:
            try:
                new_drives, removed_drives = self.usb_manager.check_for_new_drives()
                if new_drives:
                    self.usb_detected.emit(new_drives[0])
                if removed_drives:
                    self.usb_removed.emit(removed_drives[0])
                self.msleep(2000)
            except Exception as e:
                print(f"Error in USBMonitorThread: {e}")
                self.msleep(5000)

    def stop_monitoring(self):
        self.monitoring = False

class USBScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.usb_manager = USBFileManager()
        self.monitoring_thread = None
        self.blink_timer = QTimer(self)

        self.STATUS_COLORS = {
            'monitoring': '#ff9900',  # Orange
            'success': '#28a745',     # Green
            'warning': '#ffc107',     # Yellow
            'error': '#dc3545'        # Red
        }
        
        self.setup_ui()
        self.setup_timers_and_connections()
        
        try:
            self.usb_manager.cleanup_all_temp_folders()
        except Exception as e:
            print(f"Error during initial cleanup of old temp folders: {e}")

    def setup_ui(self):
        """
        Initializes the user interface using a flexible, layered layout.
        """
        # 1. Main Stacked Layout for Background/Foreground Layering
        main_layout = QStackedLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        # --- FIX: Set stacking mode to allow layering ---
        main_layout.setStackingMode(QStackedLayout.StackAll)
        self.setLayout(main_layout)

        # 2. Background Layer
        background_label = QLabel()
        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'usb_screen background.png')
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            background_label.setPixmap(pixmap)
            background_label.setScaledContents(True)
        else:
            print(f"WARNING: Background image not found at '{image_path}'")
            background_label.setStyleSheet("background-color: #e0e0e0;")

        # 3. Foreground Layer (contains all UI controls)
        foreground_widget = QWidget()
        foreground_widget.setStyleSheet("background-color: transparent;")
        
        fg_layout = QVBoxLayout(foreground_widget)
        fg_layout.setContentsMargins(40, 30, 40, 30)
        fg_layout.setSpacing(15)

        # --- UI Elements ---
        title = QLabel("INSERT USB FLASHDRIVE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #36454F; font-size: 38px; font-weight: bold;")
        title.setWordWrap(True)

        instruction = QLabel("The system will automatically detect your drive. If it doesn't appear, you can try a manual scan.")
        instruction.setAlignment(Qt.AlignCenter)
        instruction.setWordWrap(True)
        instruction.setStyleSheet("color: #36454F; font-size: 22px; line-height: 1.4;")
        instruction.setMaximumWidth(800)

        self.status_indicator = QLabel("Initializing...")
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self.status_indicator.setMinimumHeight(55)
        self.status_indicator.setStyleSheet(f"""
            QLabel {{
                color: #555; font-size: 18px; padding: 10px 20px;
                border: 2px solid #ccc; border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.1);
            }}""")

        # Button Styles
        action_button_style = """
            QPushButton {
                background-color: #1e440a; color: white; font-size: 15px;
                font-weight: bold; border: none; border-radius: 8px; 
                padding: 12px 24px;
            }
            QPushButton:hover { background-color: #2a5d1a; }
            QPushButton:pressed { background-color: #142e07; }
        """
        back_button_style = """
            QPushButton { 
                background-color: #6c757d; color: white; font-size: 14px;
                border: none; border-radius: 6px; padding: 10px 20px;
            }
            QPushButton:hover { background-color: #5a6268; }
        """
        cancel_button_style = """
            QPushButton { 
                background-color: #c82333; color: white; font-size: 14px;
                border: none; border-radius: 6px; padding: 10px 20px;
            }
            QPushButton:hover { background-color: #a51c2a; }
        """

        # Button Creation
        scan_button = QPushButton("Manual Scan")
        scan_button.setStyleSheet(action_button_style)
        
        test_button = QPushButton("TEST: Simulate PDF")
        test_button.setStyleSheet(action_button_style)
        
        clean_button = QPushButton("Clean Temp Files")
        clean_button.setStyleSheet(action_button_style)

        back_button = QPushButton("← Back to Main")
        back_button.setStyleSheet(back_button_style)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.setStyleSheet(cancel_button_style)
        
        # --- Layout Assembly ---
        fg_layout.addStretch(3)
        fg_layout.addWidget(title, 0, Qt.AlignCenter)
        fg_layout.addSpacing(10)
        fg_layout.addWidget(instruction, 0, Qt.AlignCenter)
        fg_layout.addStretch(1)
        
        status_layout = QHBoxLayout()
        status_layout.addStretch()
        status_layout.addWidget(self.status_indicator)
        status_layout.addStretch()
        fg_layout.addLayout(status_layout)
        fg_layout.addSpacing(20)

        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.addStretch()
        action_buttons_layout.addWidget(scan_button)
        action_buttons_layout.addSpacing(20)
        action_buttons_layout.addWidget(test_button)
        action_buttons_layout.addSpacing(20)
        action_buttons_layout.addWidget(clean_button)
        action_buttons_layout.addStretch()
        fg_layout.addLayout(action_buttons_layout)
        fg_layout.addStretch(4)

        nav_buttons_layout = QHBoxLayout()
        nav_buttons_layout.addWidget(back_button, 0, Qt.AlignLeft)
        nav_buttons_layout.addStretch()
        nav_buttons_layout.addWidget(cancel_button, 0, Qt.AlignRight)
        fg_layout.addLayout(nav_buttons_layout)

        # 4. Add Layers to Main Layout
        main_layout.addWidget(background_label)
        main_layout.addWidget(foreground_widget)
        
        # --- FIX: Explicitly set the foreground widget as the active one for interaction ---
        main_layout.setCurrentWidget(foreground_widget)

        # Store buttons for connecting signals
        self.scan_button = scan_button
        self.test_button = test_button
        self.clean_button = clean_button
        self.back_button = back_button
        self.cancel_button = cancel_button

    def setup_timers_and_connections(self):
        """Connect all signals and timers for the screen."""
        self.blink_timer.timeout.connect(self.blink_status)
        
        self.scan_button.clicked.connect(self.manual_scan_usb_drives)
        self.test_button.clicked.connect(self.test_simulate_files_found)
        self.clean_button.clicked.connect(self.manual_cleanup)
        self.back_button.clicked.connect(self.go_back)
        self.cancel_button.clicked.connect(self.cancel_operation)

    def on_enter(self):
        """Called when the screen becomes active."""
        print("🔄 Entering USB screen, performing initial check...")
        self.blink_timer.start(700)
        
        try:
            current_drives = self.usb_manager.get_usb_drives()
            if current_drives:
                self.handle_usb_scan_result(current_drives)
            else:
                self.start_usb_monitoring()
        except Exception as e:
            self._update_status_indicator("Error checking for USB drives.", 'error')
            print(f"Error during on_enter USB check: {e}")

    def on_leave(self):
        """Called when the screen becomes inactive."""
        print("⏹️ Leaving USB screen")
        self.stop_usb_monitoring()
        self.blink_timer.stop()

    def start_usb_monitoring(self):
        """Starts the background thread to watch for USB insertions."""
        if not self.monitoring_thread or not self.monitoring_thread.isRunning():
            self._update_status_indicator("Monitoring for USB devices...", 'monitoring')
            self.monitoring_thread = USBMonitorThread(self.usb_manager)
            self.monitoring_thread.usb_detected.connect(self.on_usb_detected)
            self.monitoring_thread.usb_removed.connect(self.on_usb_removed)
            self.monitoring_thread.start()
            print("✅ USB monitoring started")

    def stop_usb_monitoring(self):
        """Stops the background USB monitoring thread."""
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop_monitoring()
            self.monitoring_thread.wait(2000)
            self.monitoring_thread = None
            print("✅ USB monitoring stopped")

    def on_usb_detected(self, drive_path):
        """Handles the signal when a new USB drive is detected."""
        print(f"🔌 USB drive detected: {drive_path}")
        self.handle_usb_scan_result([drive_path])

    def on_usb_removed(self, drive_path):
        """Handles the signal when a USB drive is removed."""
        print(f"🔌 USB drive removed: {drive_path}")
        self._update_status_indicator("USB drive was removed.", 'warning')
        self.start_usb_monitoring()

    def manual_scan_usb_drives(self):
        """Initiates a manual scan for USB drives in a separate thread."""
        self._update_status_indicator("Scanning for USB drives...", 'monitoring')
        threading.Thread(
            target=lambda: self.handle_usb_scan_result(self.usb_manager.get_usb_drives()),
            daemon=True
        ).start()

    def handle_usb_scan_result(self, usb_drives):
        """Processes the results of a USB scan."""
        if not usb_drives:
            self._update_status_indicator("No USB drives found. Please insert a drive.", 'warning')
            self.start_usb_monitoring()
            return

        self.stop_usb_monitoring()
        
        if len(usb_drives) > 1:
            self._update_status_indicator(f"Found {len(usb_drives)} drives. Please connect only one.", 'error')
            return

        drive_path = usb_drives[0]
        self._update_status_indicator(f"USB drive found! Scanning for PDF files...", 'success')
        
        QTimer.singleShot(100, lambda: self.scan_files_from_drive(drive_path))

    def scan_files_from_drive(self, drive_path):
        """Scans the given drive for PDF files and transitions to the next screen."""
        pdf_files = self.usb_manager.scan_and_copy_pdf_files(drive_path)
        
        if pdf_files:
            self._update_status_indicator(f"Success! Found {len(pdf_files)} PDF file(s).", 'success')
            self.main_app.file_browser_screen.load_pdf_files(pdf_files)
            self.main_app.show_screen('file_browser')
        else:
            self._update_status_indicator("No PDF files were found on the USB drive.", 'error')
            QTimer.singleShot(3000, self.start_usb_monitoring)

    def test_simulate_files_found(self):
        """Simulates finding dummy PDF files for testing purposes."""
        print("\n=== TEST: Simulating PDF files found ===")
        temp_dir = self.usb_manager.destination_dir
        dummy_files = []
        try:
            for i, name in enumerate(["report.pdf", "presentation_notes.pdf"]):
                path = os.path.join(temp_dir, name)
                with open(path, 'wb') as f:
                    f.write(b"%PDF-1.4\n1 0 obj<</Type/Page>>endobj\nxref\n0 2\n0000000000 65535 f \n0000000009 00000 n \ntrailer<</Size 2/Root 1 0 R>>\nstartxref\n24\n%%EOF")
                dummy_files.append({'filename': name, 'size': 1024 * (50+i*20), 'pages': i + 2, 'path': path, 'type': '.pdf'})
            
            # This is a temporary override to inject the dummy files into the workflow
            # It avoids needing a real USB drive for testing
            self.scan_files_from_drive = lambda drive_path: self.processing_complete_simulation(dummy_files)
            self.handle_usb_scan_result(["/mnt/simulated_usb"])
            
        except Exception as e:
            QMessageBox.warning(self, "Test Error", f"Failed to create dummy files: {e}")

    def processing_complete_simulation(self, dummy_files):
        """Helper for the test simulation to bypass actual scanning."""
        self._update_status_indicator(f"Success! Found {len(dummy_files)} PDF file(s).", 'success')
        self.main_app.file_browser_screen.load_pdf_files(dummy_files)
        self.main_app.show_screen('file_browser')
        # Restore the original method after the simulation is complete
        del self.scan_files_from_drive

    def manual_cleanup(self):
        """Asks user for confirmation before cleaning temporary files."""
        reply = QMessageBox.question(self, 'Confirm Cleanup', 
                                     'This will delete all copied temporary files. Are you sure?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.usb_manager.cleanup_temp_files()
            QMessageBox.information(self, "Cleanup", "Temporary files have been cleaned.")

    def _update_status_indicator(self, text, style_key):
        """Updates the text and style of the status indicator label."""
        color_hex = self.STATUS_COLORS.get(style_key, '#ffffff')
        self.status_indicator.setText(text)
        self.status_indicator.setStyleSheet(f"""
            QLabel {{
                color: {color_hex}; font-size: 18px; font-weight: bold;
                padding: 10px 20px; border: 2px solid {color_hex}; border-radius: 8px;
                background-color: rgba({QColor(color_hex).red()}, {QColor(color_hex).green()}, {QColor(color_hex).blue()}, 0.1);
            }}""")
        
    def blink_status(self):
        """Toggles the opacity of the status indicator for a blinking effect."""
        current_style = self.status_indicator.styleSheet()
        if "0.1" in current_style:
            new_style = current_style.replace("0.1", "0.05")
        else:
            new_style = current_style.replace("0.05", "0.1")
        self.status_indicator.setStyleSheet(new_style)

    def go_back(self):
        self.main_app.show_screen('idle')

    def cancel_operation(self):
        self.main_app.show_screen('idle')