import sys
import os
import shutil
import tempfile
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSpacerItem, QSizePolicy, QDialog, QMessageBox, QListWidget
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
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

        def get_usb_drives(self):
            return []

        def check_for_new_drives(self):
            return [], []

        def scan_and_copy_pdf_files(self, source_dir):
            dummy_filename = "dummy_auto_detect.pdf"
            dummy_path = os.path.join(self.destination_dir, dummy_filename)
            try:
                with open(dummy_path, 'wb') as f:
                    f.write(b'%PDF-1.4\n1 0 obj<</Type/Page/Contents(Dummy)>>endobj\nxref\n0 2\n0000000000 00000 n\n0000000009 00000 n\ntrailer<</Size 2/Root 1 0 R>>startxref\n0\n%%EOF')
                print(f"Dummy PDF created for auto-detection: {dummy_path}")
            except Exception as e:
                print(f"Error creating dummy PDF for auto-detect: {e}")
                dummy_path = ""
            return [{
                'filename': dummy_filename,
                'size': 1024 * 500 if os.path.exists(dummy_path) else 0,
                'pages': 3,
                'path': dummy_path,
                'type': '.pdf'
            }] if os.path.exists(dummy_path) else []

        def cleanup_temp_files(self):
            if os.path.exists(self.destination_dir):
                shutil.rmtree(self.destination_dir)
                os.makedirs(self.destination_dir, exist_ok=True)
            print("Dummy cleanup_temp_files called.")

        def cleanup_all_temp_folders(self):
            temp_base_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem")
            if os.path.exists(temp_base_dir):
                shutil.rmtree(temp_base_dir)
            os.makedirs(temp_base_dir, exist_ok=True)
            print("Dummy cleanup_all_temp_folders called.")

        def get_temp_folder_info(self):
            try:
                if os.path.exists(self.destination_dir):
                    files = os.listdir(self.destination_dir)
                    total_size = sum(os.path.getsize(os.path.join(self.destination_dir, f))
                                     for f in files if os.path.isfile(os.path.join(self.destination_dir, f)))
                    return {
                        'folder_path': self.destination_dir,
                        'file_count': len(files),
                        'total_size': total_size,
                        'session_id': 'DummySession'
                    }
                return None
            except Exception as e:
                return None

        def get_drive_info(self, drive_path):
            try:
                total, used, free = shutil.disk_usage(drive_path)
                total_gb = total // (1024 ** 3)
                used_gb = used // (1024 ** 3)
                free_gb = free // (1024 ** 3)
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
                    print(f"🔌 New USB drive detected: {new_drives[0]}")
                    self.usb_detected.emit(new_drives[0])
                elif removed_drives:
                    print(f"🔌 USB drive removed: {removed_drives[0]}")
                    self.usb_removed.emit(removed_drives[0])
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
        self.setup_ui()
        self.setup_timers()
        try:
            self.usb_manager.cleanup_all_temp_folders()
        except Exception as e:
            print(f"Error cleaning up old temp folders: {e}")

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        main_frame = QFrame()
        main_frame.setStyleSheet("""
            QFrame {
                background-color: #0f0f1f;
                border: none;
            }
        """)
        frame_layout = QVBoxLayout(main_frame)
        frame_layout.setContentsMargins(50, 50, 50, 50)
        frame_layout.setSpacing(30)

        title = QLabel("INSERT USB FLASHDRIVE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 42px;
                font-weight: bold;
                margin: 20px;
            }
        """)

        instruction = QLabel("Please insert your flash drive into the USB port below. The system will automatically check for the drive.")
        instruction.setAlignment(Qt.AlignCenter)
        instruction.setWordWrap(True)
        instruction.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 28px;
                line-height: 1.4;
                margin: 20px;
            }
        """)

        nfd_label = QLabel("No flash drive found? Click the manual scan button.")
        nfd_label.setAlignment(Qt.AlignCenter)
        nfd_label.setWordWrap(True)
        nfd_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-style: italic;
                margin: 10px;
            }
        """)

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

        formats_label = QLabel("Supported format: PDF files only")
        formats_label.setAlignment(Qt.AlignCenter)
        formats_label.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 16px;
                margin: 10px;
            }
        """)

        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(20)

        scan_button = QPushButton("Manual Scan")
        scan_button.setMinimumHeight(50)
        scan_button.setStyleSheet("""
            QPushButton {
                background-color: #2d5aa0;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #3d6ab0;
            }
            QPushButton:pressed {
                background-color: #1d4a90;
            }
        """)
        scan_button.clicked.connect(self.manual_scan_usb_drives)

        test_button = QPushButton("TEST: Simulate PDF Files Found")
        test_button.setMinimumHeight(50)
        test_button.setStyleSheet("""
            QPushButton {
                background-color: #2d5aa0;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #3d6ab0;
            }
        """)
        test_button.clicked.connect(self.test_simulate_files_found)

        clean_button = QPushButton("Clean Temp Files")
        clean_button.setMinimumHeight(50)
        clean_button.setStyleSheet("""
            QPushButton {
                background-color: #2d5aa0;
                color: white;
                font-size: 18px;
                font-weight: bold;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #3d6ab0;
            }
            QPushButton:pressed {
                background-color: #1d4a90;
            }
        """)
        clean_button.clicked.connect(self.manual_cleanup)

        buttons_layout.addWidget(scan_button)
        buttons_layout.addWidget(test_button)
        buttons_layout.addWidget(clean_button)

        bottom_layout = QHBoxLayout()

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

        frame_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        frame_layout.addWidget(title)
        frame_layout.addWidget(instruction)
        frame_layout.addWidget(nfd_label)
        frame_layout.addWidget(self.status_indicator)
        frame_layout.addWidget(self.temp_info_label)
        frame_layout.addWidget(formats_label)
        frame_layout.addLayout(buttons_layout)
        frame_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        frame_layout.addLayout(bottom_layout)

        layout.addWidget(main_frame)
        self.setLayout(layout)

    def test_simulate_files_found(self):
        print("\n=== TEST: Simulating PDF files found ===")
        temp_storage_dir = self.usb_manager.destination_dir
        os.makedirs(temp_storage_dir, exist_ok=True)
        dummy_pdf_files_data = []
        dummy_filenames = ["simulated_document_1.pdf", "simulated_report_2.pdf", "another_sim_pdf_3.pdf"]
        for i, filename in enumerate(dummy_filenames):
            dummy_path = os.path.join(temp_storage_dir, filename)
            try:
                pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Page/Contents(Dummy PDF Content)>>endobj\nxref\n0 2\n0000000000 00000 n\n0000000009 00000 n\ntrailer<</Size 2/Root 1 0 R>>startxref\n0\n%%EOF"
                with open(dummy_path, 'wb') as f:
                    f.write(pdf_content)
                dummy_size = os.path.getsize(dummy_path)
                dummy_pages = i + 3
                pdf_info = {
                    'filename': filename,
                    'size': dummy_size,
                    'pages': dummy_pages,
                    'path': dummy_path,
                    'type': '.pdf'
                }
                dummy_pdf_files_data.append(pdf_info)
                print(f"Created dummy file: {dummy_path}")
            except Exception as e:
                print(f"Error creating dummy file {dummy_path}: {e}")
        if not dummy_pdf_files_data:
            QMessageBox.warning(self, "Test Warning", "Failed to create dummy PDF files for simulation.")
            return
        self.processing_complete(dummy_pdf_files_data, None)

    def update_temp_info(self):
        try:
            temp_info = self.usb_manager.get_temp_folder_info()
            if temp_info:
                self.temp_info_label.setText(f"Session: {temp_info['session_id']}")
            else:
                self.temp_info_label.setText("Session: None")
        except Exception as e:
            self.temp_info_label.setText(f"Session: Error ({e})")

    def setup_timers(self):
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self.blink_status)
        self.blink_state = True
        self.temp_info_timer = QTimer()
        self.temp_info_timer.timeout.connect(self.update_temp_info)
        self.temp_info_timer.start(5000)

    def blink_status(self):
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
        print("🔄 Entering USB screen")
        self.start_usb_monitoring()
        self.blink_timer.start(1000)
        self.update_temp_info()
        try:
            self.usb_manager.last_known_drives = set(self.usb_manager.get_usb_drives())
        except Exception as e:
            print(f"Error initializing drives: {e}")

    def on_leave(self):
        print("⏹️ Leaving USB screen")
        self.stop_usb_monitoring()
        self.blink_timer.stop()

    def start_usb_monitoring(self):
        if not self.monitoring_thread or not self.monitoring_thread.isRunning():
            self.monitoring_thread = USBMonitorThread(self.usb_manager)
            self.monitoring_thread.usb_detected.connect(self.on_usb_detected)
            self.monitoring_thread.usb_removed.connect(self.on_usb_removed)
            self.monitoring_thread.start()
            print("✅ USB monitoring started")
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
        if self.monitoring_thread and self.monitoring_thread.isRunning():
            self.monitoring_thread.stop_monitoring()
            self.monitoring_thread.wait()
            print("✅ USB monitoring stopped")

    def on_usb_detected(self, drive_path):
        print(f"🔌 USB drive detected: {drive_path}")
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
        QTimer.singleShot(1000, lambda: self.auto_process_drive(drive_path))

    def on_usb_removed(self, drive_path):
        print(f"🔌 USB drive removed: {drive_path}")
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
        # Optionally: self.start_usb_monitoring()

    def auto_process_drive(self, drive_path):
        self.stop_usb_monitoring()
        print(f"🔄 Auto-processing USB drive: {drive_path}")
        try:
            print(f"📂 Starting scan_and_copy_pdf_files for {drive_path}")
            pdf_files = self.usb_manager.scan_and_copy_pdf_files(drive_path)
            print(f"📋 Found {len(pdf_files)} PDF files")
            if pdf_files:
                self.status_indicator.setText(f"✅ Found {len(pdf_files)} PDF files! Loading preview...")
                print("🔄 Calling processing_complete...")
                self.processing_complete(pdf_files, None)
            else:
                self.status_indicator.setText("❌ No PDF files found on USB drive")
                print("⚠️ No PDF files found, restarting monitoring")
                self.start_usb_monitoring()
        except Exception as e:
            print(f"❌ Error processing USB drive: {str(e)}")
            import traceback
            traceback.print_exc()
            self.processing_error(str(e), None)

    def manual_scan_usb_drives(self):
        print("🔍 Manual USB scan initiated")
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
            usb_drives = self.usb_manager.get_usb_drives()
            print(f"📋 Manual scan found {len(usb_drives)} drives: {usb_drives}")
            QTimer.singleShot(0, lambda: self.handle_usb_scan_result(usb_drives))
        threading.Thread(target=scan_thread, daemon=True).start()

    def handle_usb_scan_result(self, usb_drives):
        if usb_drives:
            print(f"✅ Found {len(usb_drives)} USB drive(s)")
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
                QTimer.singleShot(1000, lambda: self.auto_process_drive(usb_drives[0]))
            else:
                self.show_usb_selection_dialog(usb_drives)
        else:
            print("❌ No USB drives detected")
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

    def show_usb_selection_dialog(self, usb_drives):
        dialog = QDialog(self)
        dialog.setWindowTitle("USB Drive Selection")
        dialog.setModal(True)
        dialog.setFixedSize(600, 400)
        dialog.setStyleSheet("QDialog { background-color: #2b2b2b; }")
        layout = QVBoxLayout()

        header = QLabel("Multiple USB drives detected. Select one:")
        header.setStyleSheet("color: white; font-size: 16px; margin: 10px; font-weight: bold;")
        layout.addWidget(header)

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
        """)
        for drive in usb_drives:
            try:
                drive_info = self.usb_manager.get_drive_info(drive)
                if drive_info:
                    display_text = (f"🔌 {drive_info['path']}\n"
                                    f"   💾 {drive_info['filesystem']} | "
                                    f"📊 {drive_info['free_gb']:.1f}GB free / {drive_info['total_gb']:.1f}GB total")
                else:
                    display_text = f"🔌 {drive}\n   ❌ Drive info unavailable"
                drive_list.addItem(display_text)
            except Exception as e:
                drive_list.addItem(f"🔌 {drive}\n   ❌ Error: {str(e)}")
        layout.addWidget(drive_list)

        button_layout = QHBoxLayout()
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
        """)
        def on_select():
            current_row = drive_list.currentRow()
            if current_row >= 0:
                selected_drive = usb_drives[current_row]
                dialog.accept()
                self.auto_process_drive(selected_drive)
            else:
                QMessageBox.warning(dialog, "No Selection", "Please select a USB drive first.")
        select_button.clicked.connect(on_select)
        cancel_button.clicked.connect(dialog.reject)

        button_layout.addWidget(select_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        dialog.setLayout(layout)
        dialog.exec_()

    def processing_complete(self, pdf_files, dialog):
        print("\n=== USB PROCESSING COMPLETE DEBUG ===")
        print(f"📄 PDF files found: {len(pdf_files)}")
        print(f"📋 File details: {[f['filename'] for f in pdf_files]}")
        if pdf_files and len(pdf_files) > 0:
            print("✅ Valid PDF files found, preparing transition...")
            if not hasattr(self.main_app, 'file_browser_screen'):
                print("❌ Error: file_browser_screen not found in main_app")
                QMessageBox.critical(self, "Error", "System error: PDF preview screen not available")
                return
            try:
                print("🛑 Stopping USB monitoring...")
                self.stop_usb_monitoring()
                print("📂 Loading files into browser...")
                self.main_app.file_browser_screen.load_pdf_files(pdf_files)
                print("🔄 Initiating screen transition...")
                result = self.main_app.show_screen('file_browser')
                if not result:
                    print("❌ Screen transition failed!")
                    self.start_usb_monitoring()
                    QMessageBox.warning(self, "Error", "Failed to switch to PDF preview screen")
            except Exception as e:
                print(f"❌ Error during transition: {str(e)}")
                import traceback
                traceback.print_exc()
                self.start_usb_monitoring()
                QMessageBox.critical(self, "Error", f"Failed to load PDF preview:\n{str(e)}")
        else:
            print("❌ No valid PDF files found")
            self.status_indicator.setText("No PDF files found on USB drive")
            self.start_usb_monitoring()

    def processing_error(self, error_message, dialog):
        print(f"❌ Processing error: {error_message}")
        if dialog:
            dialog.accept()
        self.status_indicator.setText(f"❌ Error: {error_message}")
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
        self.start_usb_monitoring()

    def manual_cleanup(self):
        reply = QMessageBox.question(self, 'Clean Temporary Files',
                                     'This will delete all copied PDF files from the temporary folder.\n\nAre you sure?',
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.usb_manager.cleanup_temp_files()
                self.update_temp_info()
                QMessageBox.information(self, "Cleanup Complete", "Temporary files have been deleted.")
            except Exception as e:
                QMessageBox.warning(self, "Cleanup Error", f"Error during cleanup: {e}")

    def go_back(self):
        self.main_app.show_screen('idle')

    def cancel_operation(self):
        reply = QMessageBox.question(self, 'Cancel Operation',
                                     'Are you sure you want to cancel?',
                                     QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.main_app.show_screen('idle')