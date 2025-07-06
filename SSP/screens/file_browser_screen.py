import os
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QScrollArea, QSizePolicy, QFrame,
                             QSpacerItem, QGridLayout, QDialog, QProgressBar,
                             QMessageBox, QListWidget, QListWidgetItem, QCheckBox)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QPainter, QPen, QPixmap, QImage
import threading
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("PyMuPDF not available - PDF preview will be limited")

from screens.usb_file_manager import USBFileManager
from screens.payment_dialog import PaymentCalculationDialog

class PDFButton(QPushButton):
    """Custom button for PDF file selection"""
    pdf_selected = pyqtSignal(dict)

    def __init__(self, pdf_data):
        super().__init__()
        self.pdf_data = pdf_data
        self.is_selected = False
        
        # Format PDF display text
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
    """Widget for displaying PDF page preview with selection checkbox"""
    page_selected = pyqtSignal(int, bool)  # page_num, selected
    
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
        
        # Page selection checkbox
        self.checkbox = QCheckBox(f"Page {self.page_num}")
        self.checkbox.setChecked(True)  # Default to selected
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
        
        # PDF preview area
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
        """Handle checkbox state change"""
        self.page_selected.emit(self.page_num, state == Qt.Checked)
        
        # Update visual appearance based on selection
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
        """Set the preview image"""
        self.preview_label.setPixmap(pixmap)
        self.preview_label.setText("")
    
    def set_error_message(self, error_msg):
        """Set error message"""
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
    """Thread for loading PDF previews"""
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
            pages_to_render = min(self.total_pages, actual_pages, 20)  # Limit to 20 pages for performance
            
            for page_num in range(pages_to_render):
                if not self.running:
                    break
                    
                try:
                    page = doc[page_num]
                    # Render page to pixmap
                    mat = fitz.Matrix(1.2, 1.2)  # Scale factor for better quality
                    pix = page.get_pixmap(matrix=mat)
                    
                    # Convert to QPixmap
                    img_data = pix.tobytes("ppm")
                    qimg = QImage.fromData(img_data)
                    pixmap = QPixmap.fromImage(qimg)
                    
                    # Scale to fit preview size while maintaining aspect ratio
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
        self.usb_manager = main_app.usb_screen.usb_manager  # Use the same manager instance
        self.pdf_files_data = []
        self.selected_pdf = None
        self.pdf_buttons = []
        self.page_widgets = []
        self.selected_pages = {}  # Track which pages are selected for printing
        self.preview_thread = None
        self.setup_ui()

    def setup_ui(self):
        # Main layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Set background
        self.setStyleSheet("""
            QWidget {
                background-color: #1f1f38;
            }
        """)
        
        # Header
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
        
        # Content area
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Left panel - PDF file list (25% width)
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
        
        # File list header
        self.file_header = QLabel("PDF Files (0 files)")
        self.file_header.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 18px;
                font-weight: bold;
                margin: 10px 0;
            }
        """)
        
        # File list scroll area
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
        
        # Back button
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
        
        # Right panel - PDF Preview (75% width)
        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #1f1f38;
            }
        """)
        
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)
        
        # Preview header with controls
        preview_header_layout = QHBoxLayout()
        
        self.preview_header = QLabel("Select a PDF file to preview pages")
        self.preview_header.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        
        # Page selection controls
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
        
        # Preview scroll area
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
        
        # Bottom controls
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
        
        # Add panels to content layout
        content_layout.addWidget(left_panel)
        content_layout.addWidget(right_panel)
        
        # Add to main layout
        main_layout.addWidget(header_frame)
        main_layout.addLayout(content_layout)
        
        self.setLayout(main_layout)

    def load_pdf_files(self, pdf_files):
        """Load PDF files from USB scan result"""
        print(f"Loading {len(pdf_files)} PDF files into file browser")
        
        self.pdf_files_data = []
        
        for pdf_info in pdf_files:
            pdf_data = {
                'filename': pdf_info['filename'],
                'type': 'pdf',
                'pages': pdf_info.get('pages', 1),
                'size': pdf_info['size'],
                'path': pdf_info['path']
            }
            self.pdf_files_data.append(pdf_data)
        
        # Update header
        self.file_header.setText(f"PDF Files ({len(self.pdf_files_data)} files)")
        
        # Clear and rebuild file list
        self.clear_file_list()
        self.pdf_buttons = []
        
        for pdf_data in self.pdf_files_data:
            pdf_btn = PDFButton(pdf_data)
            pdf_btn.pdf_selected.connect(self.select_pdf)
            self.pdf_buttons.append(pdf_btn)
            self.file_list_layout.insertWidget(self.file_list_layout.count() - 1, pdf_btn)
        
        # Reset preview
        self.selected_pdf = None
        self.clear_preview()
        self.page_info.setText("Select a PDF to preview pages")
        self.preview_header.setText("Select a PDF file to preview pages")
        
        print("PDF files loaded successfully")

    def clear_file_list(self):
        """Clear the file list"""
        while self.file_list_layout.count() > 1:  # Keep the stretch item
            child = self.file_list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def clear_preview(self):
        """Clear the preview area"""
        # Stop any running preview thread
        if self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.stop()
            self.preview_thread.wait()
        
        # Clear preview widgets
        while self.preview_layout.count():
            child = self.preview_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.page_widgets = []
        self.selected_pages = {}
        
        # Hide controls
        self.select_all_btn.setVisible(False)
        self.deselect_all_btn.setVisible(False)
        self.continue_btn.setVisible(False)
        self.selected_count_label.setText("")

    def select_pdf(self, pdf_data):
        """Handle PDF file selection"""
        print(f"Selected PDF: {pdf_data['filename']}")
        
        # Reset all buttons
        for btn in self.pdf_buttons:
            btn.set_selected(False)
        
        # Find and select the clicked button
        for btn in self.pdf_buttons:
            if btn.pdf_data == pdf_data:
                btn.set_selected(True)
                break

        self.selected_pdf = pdf_data
        self.preview_header.setText(f"Preview: {pdf_data['filename']} - Select pages to print")
        
        # Show PDF preview
        self.show_pdf_preview()

    def show_pdf_preview(self):
        """Show preview of selected PDF file with page selection"""
        if not self.selected_pdf:
            return
        
        print(f"Showing preview for {self.selected_pdf['filename']}")
        
        # Clear previous preview
        self.clear_preview()
        
        pdf_path = self.selected_pdf['path']
        pages = self.selected_pdf['pages']
        
        # Initialize selected pages (all selected by default)
        self.selected_pages = {i: True for i in range(1, pages + 1)}
        
        # Show page info
        self.page_info.setText(f"PDF: {pages} pages")
        self.update_selected_count()
        
        # Show controls
        self.select_all_btn.setVisible(True)
        self.deselect_all_btn.setVisible(True)
        self.continue_btn.setVisible(True)
        
        # Create page widgets (limit to 20 pages for performance)
        max_preview_pages = min(pages, 20)
        cols = 4
        
        for page_num in range(1, max_preview_pages + 1):
            row = (page_num - 1) // cols
            col = (page_num - 1) % cols
            
            page_widget = PDFPageWidget(page_num)
            page_widget.page_selected.connect(self.on_page_selected)
            self.page_widgets.append(page_widget)
            self.preview_layout.addWidget(page_widget, row, col)
        
        # If there are more pages than we can preview, add a note
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
        
        # Start loading actual PDF content
        if PYMUPDF_AVAILABLE:
            self.preview_thread = PDFPreviewThread(pdf_path, max_preview_pages)
            self.preview_thread.preview_ready.connect(self.on_preview_ready)
            self.preview_thread.error_occurred.connect(self.on_preview_error)
            self.preview_thread.start()
        else:
            # Show placeholder if PyMuPDF not available
            for widget in self.page_widgets:
                widget.preview_label.setText(f"Page {widget.page_num}\n\nPDF Preview\nRequires PyMuPDF")

    def on_page_selected(self, page_num, selected):
        """Handle page selection change"""
        self.selected_pages[page_num] = selected
        self.update_selected_count()

    def update_selected_count(self):
        """Update the selected pages count display"""
        selected_count = sum(1 for selected in self.selected_pages.values() if selected)
        total_pages = len(self.selected_pages)
        
        self.selected_count_label.setText(f"Selected: {selected_count}/{total_pages} pages")
        
        # Enable/disable continue button based on selection
        self.continue_btn.setEnabled(selected_count > 0)

    def select_all_pages(self):
        """Select all pages"""
        for page_num in self.selected_pages:
            self.selected_pages[page_num] = True
        
        # Update checkboxes
        for widget in self.page_widgets:
            widget.checkbox.setChecked(True)
        
        self.update_selected_count()

    def deselect_all_pages(self):
        """Deselect all pages"""
        for page_num in self.selected_pages:
            self.selected_pages[page_num] = False
        
        # Update checkboxes
        for widget in self.page_widgets:
            widget.checkbox.setChecked(False)
        
        self.update_selected_count()

    def continue_to_payment(self):
        """Continue to payment calculation"""
        if not self.selected_pdf:
            return
        
        selected_count = sum(1 for selected in self.selected_pages.values() if selected)
        
        if selected_count == 0:
            QMessageBox.warning(self, "No Pages Selected", "Please select at least one page to print.")
            return
        
        # Create modified PDF data with selected pages
        pdf_data_for_payment = self.selected_pdf.copy()
        pdf_data_for_payment['selected_pages'] = [page for page, selected in self.selected_pages.items() if selected]
        pdf_data_for_payment['pages'] = selected_count  # Override page count with selected pages
        
        print(f"Proceeding to payment for {selected_count} selected pages")
        
        # Show payment calculation dialog
        payment_dialog = PaymentCalculationDialog(pdf_data_for_payment, self)
        payment_dialog.payment_completed.connect(self.on_payment_completed)
        payment_dialog.exec_()

    def on_payment_completed(self, payment_info):
        """Handle completed payment"""
        print("Payment completed successfully")
        QMessageBox.information(self, "Payment Successful", 
                              f"Payment completed!\n\n"
                              f"File: {payment_info['pdf_data']['filename']}\n"
                              f"Pages to print: {payment_info['copies']} copies of {len(payment_info['pdf_data']['selected_pages'])} pages\n"
                              f"Total cost: ₱{payment_info['total_cost']:.2f}\n\n"
                              f"Your PDF is ready for printing!")

    def on_preview_ready(self, page_num, pixmap):
        """Handle when a PDF preview is ready"""
        if page_num <= len(self.page_widgets):
            widget = self.page_widgets[page_num - 1]
            widget.set_preview_image(pixmap)

    def on_preview_error(self, page_num, error_msg):
        """Handle PDF preview errors"""
        if page_num <= len(self.page_widgets):
            widget = self.page_widgets[page_num - 1]
            widget.set_error_message(error_msg)

    def go_back(self):
        """Go back to USB screen"""
        self.main_app.show_screen('usb')

    def on_enter(self):
        """Called when screen becomes active"""
        print("File browser screen entered")

    def on_leave(self):
        """Called when leaving screen"""
        # Stop any running preview thread
        if self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.stop()
            self.preview_thread.wait()
        print("File browser screen left")
