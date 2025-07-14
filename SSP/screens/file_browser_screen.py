print("DEBUG: file_browser_screen.py: Module start.")

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea,
    QFrame, QMessageBox, QGridLayout, QCheckBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QPixmap, QImage

print("DEBUG: file_browser_screen.py: PyQt5 imports complete.")

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
    print("DEBUG: file_browser_screen.py: PyMuPDF (fitz) imported successfully.")
except ImportError as e:
    PYMUPDF_AVAILABLE = False
    print(f"DEBUG: file_browser_screen.py: PyMuPDF (fitz) not available - PDF preview will be limited. Error: {e}")

try:
    from screens.usb_file_manager import USBFileManager
    print("DEBUG: file_browser_screen.py: USBFileManager imported successfully.")
except ImportError as e:
    print(f"DEBUG: file_browser_screen.py: Failed to import USBFileManager: {e}")
    # Fallback/Dummy for testing if USBFileManager itself is broken
    class USBFileManager:
        def __init__(self):
            print("DEBUG: Using dummy USBFileManager in file_browser_screen.py")
        def get_temp_folder_info(self): return None
        def estimate_pdf_pages_fast(self, size): return 1
        # Add other methods it might call if needed, e.g., scan_and_copy_pdf_files
        def scan_and_copy_pdf_files(self, path): return []

try:
    from screens.payment_dialog import PaymentScreen
    print("DEBUG: file_browser_screen.py: PaymentScreen imported successfully.")
except ImportError as e:
    print(f"DEBUG: file_browser_screen.py: Failed to import PaymentScreen: {e}")
    # Fallback/Dummy for testing if PaymentScreen itself is broken
    class PaymentScreen:
        def __init__(self, main_app, pdf_data):
            print("DEBUG: Using dummy PaymentScreen in file_browser_screen.py")
        def payment_completed(): pass
        def go_back_to_viewer(): pass


print("DEBUG: file_browser_screen.py: All internal imports complete. Attempting to define FileBrowserScreen class.")

class PDFButton(QPushButton):
    pdf_selected = pyqtSignal(dict)

    def __init__(self, pdf_data):
        super().__init__()
        self.pdf_data = pdf_data
        self.is_selected = False

        filename = pdf_data['filename']
        size_mb = pdf_data.get('size', 0) / (1024 * 1024)
        pages = pdf_data.get('pages', 1)
        self.setText(f"📄 {filename}\n({size_mb:.1f}MB, ~{pages} pages)")
        self.setMinimumHeight(80)
        self.setMaximumHeight(80)
        self.setStyleSheet(self.get_normal_style())
        self.clicked.connect(self.on_click)

    def get_normal_style(self):
        return """
            QPushButton {
                background-color: #333366;
                color: white;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 10px;
                text-align: left;
                font-size: 12px;
                margin: 2px;
            }
            QPushButton:hover {
                background-color: #404080;
                border: 1px solid #6666aa;
            }
        """

    def get_selected_style(self):
        return """
            QPushButton {
                background-color: #4d80cc;
                color: white;
                border: 3px solid #6699ff;
                border-radius: 8px;
                padding: 10px;
                text-align: left;
                font-size: 12px;
                font-weight: bold;
                margin: 2px;
            }
        """

    def on_click(self):
        self.pdf_selected.emit(self.pdf_data)

    def set_selected(self, selected):
        self.is_selected = selected
        if selected:
            self.setStyleSheet(self.get_selected_style())
        else:
            self.setStyleSheet(self.get_normal_style())

class PDFPageWidget(QFrame):
    page_selected = pyqtSignal(int, bool)

    def __init__(self, page_num=1):
        super().__init__()
        self.page_num = page_num
        self.setFixedSize(200, 300)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 2px solid #ddd;
                border-radius: 8px;
                margin: 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.checkbox = QCheckBox(f"Page {self.page_num}")
        self.checkbox.setChecked(True)
        self.checkbox.setStyleSheet("""
            QCheckBox {
                color: #333;
                font-weight: bold;
                font-size: 11px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
            }
            QCheckBox::indicator:unchecked {
                background-color: white;
                border: 2px solid #ccc;
            }
        """)
        self.checkbox.stateChanged.connect(self.on_checkbox_changed)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(240)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f9f9f9;
                border: 1px solid #ddd;
                border-radius: 4px;
                color: #666;
                font-size: 10px;
            }
        """)
        self.preview_label.setText(f"Loading\nPage {self.page_num}...")

        layout.addWidget(self.checkbox)
        layout.addWidget(self.preview_label)

    def on_checkbox_changed(self, state):
        self.page_selected.emit(self.page_num, state == Qt.Checked)
        if state == Qt.Checked:
            self.setStyleSheet("""
                QFrame {
                    background-color: white;
                    border: 3px solid #4CAF50;
                    border-radius: 8px;
                    margin: 5px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background-color: #f5f5f5;
                    border: 2px solid #ccc;
                    border-radius: 8px;
                    margin: 5px;
                }
            """)

    def set_preview_image(self, pixmap):
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setText("")

    def set_error_message(self, error_msg):
        self.preview_label.setText(f"Page {self.page_num}\n\nError:\n{error_msg}")
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #ffeeee;
                border: 1px solid #ffaaaa;
                border-radius: 4px;
                color: #cc0000;
                font-size: 9px;
            }
        """)

class PDFPreviewThread(QThread):
    preview_ready = pyqtSignal(int, QPixmap)
    error_occurred = pyqtSignal(int, str)

    def __init__(self, pdf_path, total_pages):
        super().__init__()
        self.pdf_path = pdf_path
        self.total_pages = total_pages
        self.running = True

    def run(self):
        if not PYMUPDF_AVAILABLE:
            for i in range(min(self.total_pages, 10)):
                if not self.running:
                    break
                self.error_occurred.emit(i + 1, "PyMuPDF not available")
            return

        try:
            doc = fitz.open(self.pdf_path)
            actual_pages = len(doc)
            pages_to_render = min(self.total_pages, actual_pages, 20)
            for page_num in range(pages_to_render):
                if not self.running:
                    break
                try:
                    page = doc[page_num]
                    mat = fitz.Matrix(1.2, 1.2)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("ppm")
                    qimg = QImage.fromData(img_data)
                    pixmap = QPixmap.fromImage(qimg)
                    scaled_pixmap = pixmap.scaled(180, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.preview_ready.emit(page_num + 1, scaled_pixmap)
                except Exception as e:
                    self.error_occurred.emit(page_num + 1, str(e))
            doc.close()
        except Exception as e:
            self.error_occurred.emit(1, f"Failed to open PDF: {str(e)}")

    def stop(self):
        self.running = False

class FileBrowserScreen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        
        # Initialize class variables first
        self.pdf_files_data = []
        self.selected_pdf = None
        self.pdf_buttons = []
        self.page_widgets = []
        self.selected_pages = None
        self.pdf_page_selections = {}
        self.preview_thread = None
        self.restore_payment_data = None

        # Link to USB manager
        try:
            self.usb_manager = main_app.usb_screen.usb_manager
            print("DEBUG: FileBrowserScreen: Successfully linked to usb_manager from usb_screen.")
        except AttributeError:
            print("ERROR: FileBrowserScreen: Could not link to usb_manager from usb_screen. Creating a dummy.")
            self.usb_manager = USBFileManager()

        # Setup the UI after initializing variables
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.setStyleSheet("""
            QWidget {
                background-color: #1f1f38;
            }
        """)

        header_frame = QFrame()
        header_frame.setFixedHeight(60)
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #2a2a4a;
                border-bottom: 2px solid #333;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 10, 20, 10)
        self.main_header = QLabel("PDF File Browser - Select Pages to Print")
        self.main_header.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24px;
                font-weight: bold;
            }
        """)
        header_layout.addWidget(self.main_header)
        header_layout.addStretch()

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        left_panel = QFrame()
        left_panel.setFixedWidth(350)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #1f1f38;
                border-right: 2px solid #333;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(15, 20, 15, 20)
        left_layout.setSpacing(15)
        self.file_header = QLabel("PDF Files (0 files)")
        self.file_header.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
                margin: 10px 0;
            }
        """)
        file_scroll = QScrollArea()
        file_scroll.setWidgetResizable(True)
        file_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #444;
                border-radius: 6px;
                background-color: #2a2a4a;
            }
            QScrollBar:vertical {
                background-color: #333;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666;
                border-radius: 6px;
                min-height: 20px;
            }
        """)
        self.file_list_widget = QWidget()
        self.file_list_layout = QVBoxLayout(self.file_list_widget)
        self.file_list_layout.setSpacing(5)
        self.file_list_layout.addStretch()
        file_scroll.setWidget(self.file_list_widget)
        back_btn = QPushButton("← Back to USB")
        back_btn.setMinimumHeight(40)
        back_btn.setStyleSheet("""
            QPushButton {
                background-color: #804d4d;
                color: white;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #905d5d;
            }
        """)
        back_btn.clicked.connect(self.go_back)
        left_layout.addWidget(self.file_header)
        left_layout.addWidget(file_scroll)
        left_layout.addWidget(back_btn)

        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #1f1f38;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)
        preview_header_layout = QHBoxLayout()
        self.preview_header = QLabel("Select a PDF file to preview pages")
        self.preview_header.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        self.select_all_btn = QPushButton("Select All Pages")
        self.select_all_btn.setVisible(False)
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.select_all_btn.clicked.connect(self.select_all_pages)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setVisible(False)
        self.deselect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        self.deselect_all_btn.clicked.connect(self.deselect_all_pages)
        preview_header_layout.addWidget(self.preview_header)
        preview_header_layout.addStretch()
        preview_header_layout.addWidget(self.select_all_btn)
        preview_header_layout.addWidget(self.deselect_all_btn)
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #444;
                border-radius: 6px;
                background-color: #2a2a4a;
            }
            QScrollBar:vertical {
                background-color: #333;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666;
                border-radius: 6px;
                min-height: 20px;
            }
        """)
        self.preview_widget = QWidget()
        self.preview_layout = QGridLayout(self.preview_widget)
        self.preview_layout.setSpacing(10)
        self.preview_scroll.setWidget(self.preview_widget)
        bottom_controls = QHBoxLayout()
        bottom_controls.setSpacing(15)
        self.page_info = QLabel("No PDF selected")
        self.page_info.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 14px;
            }
        """)
        self.selected_count_label = QLabel("")
        self.selected_count_label.setStyleSheet("""
            QLabel {
                color: #4CAF50;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self.continue_btn = QPushButton("Continue to Payment →")
        self.continue_btn.setMinimumHeight(45)
        self.continue_btn.setVisible(False)
        self.continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.continue_btn.clicked.connect(self.continue_to_payment)
        bottom_controls.addWidget(self.page_info)
        bottom_controls.addWidget(self.selected_count_label)
        bottom_controls.addStretch()
        bottom_controls.addWidget(self.continue_btn)
        right_layout.addLayout(preview_header_layout)
        right_layout.addWidget(self.preview_scroll)
        right_layout.addLayout(bottom_controls)
        content_layout.addWidget(left_panel)
        content_layout.addWidget(right_panel)
        main_layout.addWidget(header_frame)
        main_layout.addLayout(content_layout)
        self.setLayout(main_layout)

    def load_pdf_files(self, pdf_files):
        """Load PDF files into the browser view"""
        print("\n=== FILE BROWSER LOADING DEBUG ===")
        print(f"📥 Received {len(pdf_files)} files to load")
    
        try:
            self.pdf_files_data = []
            self.pdf_page_selections = {}  # reset selections
            
            for pdf_info in pdf_files:
                print(f"📄 Processing: {pdf_info['filename']}")
                pdf_data = {
                    'filename': pdf_info['filename'],
                    'type': 'pdf',
                    'pages': pdf_info.get('pages', 1),
                    'size': pdf_info['size'],
                    'path': pdf_info['path']
                }
                self.pdf_files_data.append(pdf_data)
            
            print(f"📋 Updating UI for {len(self.pdf_files_data)} files")
            self.file_header.setText(f"PDF Files ({len(self.pdf_files_data)} files)")
            self.clear_file_list()
            
            self.pdf_buttons = []
            for pdf_data in self.pdf_files_data:
                pdf_btn = PDFButton(pdf_data)
                pdf_btn.pdf_selected.connect(self.select_pdf)
                self.pdf_buttons.append(pdf_btn)
                self.file_list_layout.insertWidget(
                    self.file_list_layout.count() - 1, pdf_btn)
            
            print("🔄 Clearing preview area")
            self.selected_pdf = None
            self.selected_pages = None
            self.clear_preview()
            
            if self.pdf_files_data:
                print("✅ Auto-selecting first PDF")
                self.select_pdf(self.pdf_files_data[0])
            
            print("✅ PDF loading complete")
            
        except Exception as e:
            print(f"❌ Error loading PDFs: {str(e)}")
            import traceback
            traceback.print_exc()

    def clear_file_list(self):
        while self.file_list_layout.count() > 1:
            child = self.file_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def clear_preview(self):
        if self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.stop()
            self.preview_thread.wait()
        while self.preview_layout.count():
            child = self.preview_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.page_widgets = []
        self.select_all_btn.setVisible(False)
        self.deselect_all_btn.setVisible(False)
        self.continue_btn.setVisible(False)
        self.selected_count_label.setText("")

    def select_pdf(self, pdf_data):
        print(f"DEBUG: FileBrowserScreen: select_pdf called for {pdf_data['filename']}")
        # Save the current selection before switching PDFs
        if self.selected_pdf is not None and self.selected_pages is not None:
            self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        self.selected_pdf = pdf_data

        # Load or initialize selection state for the new PDF
        if pdf_data['path'] in self.pdf_page_selections:
            self.selected_pages = self.pdf_page_selections[pdf_data['path']].copy()
        else:
            self.selected_pages = {i: True for i in range(1, pdf_data['pages'] + 1)}

        for btn in self.pdf_buttons:
            btn.set_selected(btn.pdf_data == pdf_data)
        self.preview_header.setText(f"Preview: {pdf_data['filename']} - Select pages to print")
        self.show_pdf_preview()

    def show_pdf_preview(self):
        print("DEBUG: FileBrowserScreen: show_pdf_preview called.")
        if not self.selected_pdf:
            print("DEBUG: No PDF selected for preview.")
            return
        self.clear_preview()
        pdf_path = self.selected_pdf['path']
        pages = self.selected_pdf['pages']

        self.page_info.setText(f"PDF: {pages} pages")
        self.update_selected_count()
        self.select_all_btn.setVisible(True)
        self.deselect_all_btn.setVisible(True)
        self.continue_btn.setVisible(True)

        max_preview_pages = min(pages, 20)
        cols = 4
        for page_num in range(1, max_preview_pages + 1):
            row = (page_num - 1) // cols
            col = (page_num - 1) % cols
            page_widget = PDFPageWidget(page_num)
            page_widget.page_selected.connect(self.on_page_selected)
            page_widget.checkbox.setChecked(self.selected_pages.get(page_num, True))
            self.page_widgets.append(page_widget)
            self.preview_layout.addWidget(page_widget, row, col)
        if pages > 20:
            note_label = QLabel(f"... and {pages - 20} more pages\n(All pages selected by default)")
            note_label.setAlignment(Qt.AlignCenter)
            note_label.setStyleSheet("""
                QLabel {
                    color: #888;
                    font-size: 12px;
                    font-style: italic;
                    padding: 20px;
                }
            """)
            row = (max_preview_pages - 1) // cols + 1
            self.preview_layout.addWidget(note_label, row, 0, 1, cols)
        if PYMUPDF_AVAILABLE:
            print(f"DEBUG: Starting PDFPreviewThread for {pdf_path} with {max_preview_pages} pages.")
            self.preview_thread = PDFPreviewThread(pdf_path, max_preview_pages)
            self.preview_thread.preview_ready.connect(self.on_preview_ready)
            self.preview_thread.error_occurred.connect(self.on_preview_error)
            self.preview_thread.start()
        else:
            print("DEBUG: PyMuPDF not available, showing placeholder text for preview.")
            for widget in self.page_widgets:
                widget.preview_label.setText(f"Page {widget.page_num}\n\nPDF Preview\nRequires PyMuPDF")

    def on_page_selected(self, page_num, selected):
        print(f"DEBUG: Page {page_num} selected: {selected}")
        self.selected_pages[page_num] = selected
        # Always keep the per-PDF storage up-to-date
        if self.selected_pdf:
            self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        self.update_selected_count()

    def update_selected_count(self):
        if not self.selected_pages:
            return
        selected_count = sum(1 for selected in self.selected_pages.values() if selected)
        total_pages = len(self.selected_pages)
        self.selected_count_label.setText(f"Selected: {selected_count}/{total_pages} pages")
        self.continue_btn.setEnabled(selected_count > 0)

    def select_all_pages(self):
        print("DEBUG: Select All Pages clicked.")
        if not self.selected_pages:
            return
        for page_num in self.selected_pages:
            self.selected_pages[page_num] = True
        if self.selected_pdf:
            self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        for widget in self.page_widgets:
            widget.checkbox.setChecked(True)
        self.update_selected_count()

    def deselect_all_pages(self):
        print("DEBUG: Deselect All Pages clicked.")
        if not self.selected_pages:
            return
        for page_num in self.selected_pages:
            self.selected_pages[page_num] = False
        if self.selected_pdf:
            self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        for widget in self.page_widgets:
            widget.checkbox.setChecked(False)
        self.update_selected_count()

    def continue_to_payment(self):
        print("DEBUG: Continue to Payment clicked.")
        if not self.selected_pdf:
            print("DEBUG: No PDF selected to continue to payment.")
            return
        selected_pages_list = [page for page, selected in self.selected_pages.items() if selected]
        selected_count = len(selected_pages_list)
        if selected_count == 0:
            QMessageBox.warning(self, "No Pages Selected", "Please select at least one page to print.")
            return

        pdf_data_for_payment = {
            'filename': self.selected_pdf['filename'],
            'type': 'pdf',
            'pages': selected_count,  # <-- Only selected pages count!
            'size': self.selected_pdf['size'],
            'path': self.selected_pdf['path'],
            'selected_pages': selected_pages_list,
            'total_pages': self.selected_pdf['pages'],
            'all_pages_state': self.selected_pages.copy()
        }

        payment_screen = PaymentScreen(self.main_app, pdf_data_for_payment)
        payment_screen.payment_completed.connect(self.on_payment_completed)
        payment_screen.go_back_to_viewer.connect(self.restore_from_payment)
        stack = self.main_app.stacked_widget
        for i in range(stack.count()):
            widget = stack.widget(i)
            if isinstance(widget, PaymentScreen):
                stack.removeWidget(widget)
                widget.deleteLater()
                break
        stack.addWidget(payment_screen)
        stack.setCurrentWidget(payment_screen)
        print("DEBUG: Switched to PaymentScreen.")

    def restore_from_payment(self, payment_data):
        print("DEBUG: Restoring from PaymentScreen.")
        if "pdf_data" in payment_data:
            for pdf_data in self.pdf_files_data:
                if pdf_data['path'] == payment_data["pdf_data"]["path"]:
                    self.selected_pdf = pdf_data
                    break
            # Restore the page states
            if "all_pages_state" in payment_data["pdf_data"]:
                self.selected_pages = payment_data["pdf_data"]["all_pages_state"].copy()
                self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
            else:
                selected_pages_list = payment_data["pdf_data"].get("selected_pages", [])
                total_pages = payment_data["pdf_data"].get("total_pages") or payment_data["pdf_data"].get("pages")
                if total_pages:
                    self.selected_pages = {page: (page in selected_pages_list) for page in range(1, total_pages + 1)}
                else:
                    self.selected_pages = {page: True for page in selected_pages_list}
                self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        # Reshow the current PDF selection state
        self.select_pdf(self.selected_pdf)
        self.main_app.stacked_widget.setCurrentWidget(self)
        print("DEBUG: Returned to FileBrowserScreen from PaymentScreen.")

    def on_payment_completed(self, payment_info):
        print("DEBUG: Payment completed signal received.")
        QMessageBox.information(self, "Payment Successful",
            f"Payment completed!\n\n"
            f"File: {payment_info['pdf_data']['filename']}\n"
            f"Pages to print: {payment_info['copies']} copies of {len(payment_info['pdf_data']['selected_pages'])} pages\n"
            f"Total cost: ₱{payment_info['total_cost']:.2f}\n\n"
            f"Your PDF is ready for printing!"
        )
        stack = self.main_app.stacked_widget
        stack.setCurrentWidget(self)
        for i in range(stack.count()):
            widget = stack.widget(i)
            if isinstance(widget, PaymentScreen):
                stack.removeWidget(widget)
                widget.deleteLater()
                break
        print("DEBUG: Payment completion message shown and returned to FileBrowserScreen.")

    def on_preview_ready(self, page_num, pixmap):
        if page_num <= len(self.page_widgets):
            widget = self.page_widgets[page_num - 1]
            widget.set_preview_image(pixmap)
            # print(f"DEBUG: Preview ready for page {page_num}") # Too verbose, commented out

    def on_preview_error(self, page_num, error_msg):
        if page_num <= len(self.page_widgets):
            widget = self.page_widgets[page_num - 1]
            widget.set_error_message(error_msg)
            print(f"ERROR: Preview error for page {page_num}: {error_msg}")

    def go_back(self):
        print("DEBUG: Going back to USB screen from FileBrowserScreen.")
        self.main_app.show_screen('usb')

    def on_enter(self):
        print("DEBUG: FileBrowserScreen entered.")
        # If returning from payment, restore previous state
        if self.restore_payment_data:
            self.restore_from_payment(self.restore_payment_data)
            self.restore_payment_data = None
        # Otherwise, if files were loaded, ensure first one is selected
        elif self.pdf_files_data and not self.selected_pdf:
            print("DEBUG: FileBrowserScreen: Entering with files, auto-selecting first PDF.")
            self.select_pdf(self.pdf_files_data[0])

    def on_leave(self):
        print("DEBUG: FileBrowserScreen left.")
        if self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.stop()
            self.preview_thread.wait()
        print("DEBUG: FileBrowserScreen: Preview thread stopped on leave.")

print("DEBUG: file_browser_screen.py: Module end.")