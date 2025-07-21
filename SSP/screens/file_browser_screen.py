import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea,
    QFrame, QMessageBox, QGridLayout, QCheckBox, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QPixmap, QImage
from screens.pdf_preview_widget import PDFPreviewWidget

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("PyMuPDF not available - PDF preview will be limited")

try:
    from screens.usb_file_manager import USBFileManager
except ImportError:
    class USBFileManager:
        def __init__(self): pass

try:
    from screens.payment_dialog import PaymentScreen
except ImportError:
    class PaymentScreen:
        def __init__(self, main_app, pdf_data): pass

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
    page_selected = pyqtSignal(int)
    page_checkbox_clicked = pyqtSignal(int, bool)
    def __init__(self, page_num=1, checked=True):
        super().__init__()
        self.page_num = page_num
        self.setFixedSize(200, 300)
        self.setup_ui(checked)
    def setup_ui(self, checked):
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
        self.checkbox.setChecked(checked)
        self.checkbox.setStyleSheet("""
            QCheckBox {
                color: #333;
                font-size: 14px;
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
        self.checkbox.clicked.connect(self.on_checkbox_clicked)
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
        self.setMouseTracking(True)
    def mousePressEvent(self, event):
        if not self.checkbox.geometry().contains(event.pos()):
            self.page_selected.emit(self.page_num)
    def on_checkbox_clicked(self, checked):
        self.page_checkbox_clicked.emit(self.page_num, checked)
        if checked:
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
        self.preview_label.clear()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setPixmap(pixmap)
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
    # Fixed preview area for single page mode
    SINGLE_PAGE_PREVIEW_WIDTH = 360
    SINGLE_PAGE_PREVIEW_HEIGHT = 460

    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        try:
            self.usb_manager = main_app.usb_screen.usb_manager
        except Exception:
            self.usb_manager = USBFileManager()
        self.pdf_files_data = []
        self.selected_pdf = None
        self.pdf_buttons = []
        self.page_widgets = []
        self.selected_pages = None
        self.pdf_page_selections = {}
        self.preview_thread = None
        self.restore_payment_data = None
        self.view_mode = 'all'
        self.single_page_index = 1
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
        self.main_header = QLabel("PDF File Browser")
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
        left_panel.setFixedWidth(220)
        left_panel.setStyleSheet("""
            QFrame {
                background-color: #1f1f38;
                border: none;
            }
        """)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 20, 10, 20)
        left_layout.setSpacing(10)
        self.file_header = QLabel("PDF Files (0 files)")
        self.file_header.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                font-weight: bold;
                margin: 6px 0;
            }
        """)
        file_scroll = QScrollArea()
        file_scroll.setWidgetResizable(True)
        file_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
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

        left_layout.addWidget(self.file_header)
        left_layout.addWidget(file_scroll)

        right_panel = QFrame()
        right_panel.setStyleSheet("""
            QFrame {
                background-color: #1f1f38;
            }
        """)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(20, 20, 20, 20)
        right_layout.setSpacing(15)

        # View mode buttons
        view_mode_layout = QHBoxLayout()
        view_mode_layout.setSpacing(10)
        common_btn_style = """
            QPushButton {
                background-color: #2d5aa0;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 14px;
                height: 22px;
                min-height: 22px;
                max-height: 22px;
                padding: 8px 18px;
            }
            QPushButton:checked {
                background-color: #3673c9;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #3673c9;
                color: #ffffff;
            }
        """
        self.view_all_btn = QPushButton("All Pages View")
        self.view_single_btn = QPushButton("Single Page View")
        self.view_all_btn.setCheckable(True)
        self.view_single_btn.setCheckable(True)
        self.view_all_btn.setChecked(True)
        self.view_all_btn.clicked.connect(self.set_all_pages_view)
        self.view_single_btn.clicked.connect(self.set_single_page_view)
        self.view_all_btn.setStyleSheet(common_btn_style)
        self.view_single_btn.setStyleSheet(common_btn_style)
        view_mode_layout.addStretch()
        view_mode_layout.addWidget(self.view_all_btn)
        view_mode_layout.addWidget(self.view_single_btn)

        preview_header_layout = QHBoxLayout()
        self.preview_header = QLabel("Select a PDF file to preview pages")
        self.preview_header.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 18px;
                font-weight: bold;
            }
        """)
        preview_header_layout.addWidget(self.preview_header)
        preview_header_layout.addStretch()
        preview_header_layout.addLayout(view_mode_layout)
        self.select_all_btn = QPushButton("Select All Pages")
        self.select_all_btn.setVisible(False)
        self.select_all_btn.setStyleSheet(common_btn_style + """
            QPushButton {
                background-color: #4CAF50;
            }
            QPushButton:hover, QPushButton:checked {
                background-color: #45a049;
            }
        """)
        self.select_all_btn.clicked.connect(self.select_all_pages)
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setVisible(False)
        self.deselect_all_btn.setStyleSheet(common_btn_style + """
            QPushButton {
                background-color: #ff9800;
            }
            QPushButton:hover, QPushButton:checked {
                background-color: #f57c00;
            }
        """)
        self.deselect_all_btn.clicked.connect(self.deselect_all_pages)
        preview_header_layout.addWidget(self.select_all_btn)
        preview_header_layout.addWidget(self.deselect_all_btn)
        self.preview_scroll = QScrollArea()
        self.preview_scroll.setWidgetResizable(True)
        self.preview_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
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

    
        # Single Page View with Zoom Controls
        self.single_page_widget = QWidget()
        self.single_page_layout = QVBoxLayout(self.single_page_widget)
        self.single_page_layout.setSpacing(8)
        self.single_page_layout.setAlignment(Qt.AlignVCenter)

        # Navigation and zoom controls
        nav_layout = QHBoxLayout()
        nav_btn_style = """
            QPushButton {
                background-color: #2d5aa0;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                width: 40px;
                height: 40px;
                min-width: 40px;
                max-width: 40px;
                min-height: 40px;
                max-height: 40px;
                padding: 0;
                font-weight: bold;
            }
            QPushButton:pressed, QPushButton:checked {
                background-color: #3673c9;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #3673c9;
                color: #ffffff;
            }
        """
        
        # Page navigation
        self.prev_page_btn = QPushButton("←")
        self.prev_page_btn.setStyleSheet(nav_btn_style)
        self.next_page_btn = QPushButton("→")
        self.next_page_btn.setStyleSheet(nav_btn_style)
        
        # Page indicator
        self.page_input = QLabel("1")
        self.page_input.setStyleSheet("""
            QLabel {
                background: #222;
                color: #ffffff;
                font-size: 13px;
                min-width: 40px;
                max-width: 40px;
                border-radius: 3px;
                padding: 1px 4px;
                border: 1px solid #888;
                qproperty-alignment: AlignCenter;
            }
        """)
        
        # Zoom controls
        zoom_btn_style = """
            QPushButton {
                background-color: #4CAF50;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                font-size: 18px;
                width: 40px;
                height: 40px;
                min-width: 40px;
                max-width: 40px;
                min-height: 40px;
                max-height: 40px;
                padding: 0;
                font-weight: bold;
            }
            QPushButton:pressed, QPushButton:checked {
                background-color: #45a049;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #45a049;
                color: #ffffff;
            }
        """
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setStyleSheet(zoom_btn_style)
        self.zoom_out_btn = QPushButton("−")
        self.zoom_out_btn.setStyleSheet(zoom_btn_style)
        self.zoom_reset_btn = QPushButton("⌂")  # Home/reset icon
        self.zoom_reset_btn.setStyleSheet(zoom_btn_style)

        # Zoom label style (merged)
        zoom_label_style = """
            QLabel {
                background: #333;
                color: #fff;
                font-size: 12px;
                min-width: 45px;
                max-width: 45px;
                border-radius: 3px;
                padding: 2px 4px;
                border: 1px solid #555;
                qproperty-alignment: AlignCenter;
                margin: 0 5px;
            }
        """
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet(zoom_label_style)
        
        # Zoom level indicator
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet("""
            QLabel {
                background: #333;
                color: #ffffff;
                font-size: 12px;
                min-width: 45px;
                max-width: 45px;
                border-radius: 3px;
                padding: 2px 4px;
                border: 1px solid #555;
                qproperty-alignment: AlignCenter;
            }
        """)
        
        # Layout navigation controls
        nav_layout.addWidget(self.prev_page_btn)
        nav_layout.addWidget(self.page_input)
        nav_layout.addWidget(self.next_page_btn)
        nav_layout.addStretch()
        
        # Add zoom controls
        nav_layout.addWidget(QLabel("Zoom:"))
        nav_layout.addWidget(self.zoom_out_btn)
        nav_layout.addWidget(self.zoom_label)
        nav_layout.addWidget(self.zoom_in_btn)
        nav_layout.addWidget(self.zoom_reset_btn)
        
        # Connect signals
        self.prev_page_btn.clicked.connect(self.prev_single_page)
        self.next_page_btn.clicked.connect(self.next_single_page)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        self.zoom_reset_btn.clicked.connect(self.zoom_reset)
        
        self.single_page_layout.addLayout(nav_layout)
        
        # Checkbox
        self.single_page_checkbox = QCheckBox("Select this page")
        self.single_page_checkbox.setStyleSheet("""
            QCheckBox {
                color: #fff;
                font-size: 13px;
            }
        """)
        self.single_page_checkbox.stateChanged.connect(self.single_page_checkbox_changed)
        self.single_page_layout.addWidget(self.single_page_checkbox)
        
        # Enhanced preview widget with zoom support
        self.single_page_preview = PDFPreviewWidget()
        self.single_page_preview.setFixedSize(self.SINGLE_PAGE_PREVIEW_WIDTH, self.SINGLE_PAGE_PREVIEW_HEIGHT)
        self.single_page_preview.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.single_page_layout.addWidget(self.single_page_preview, 0, Qt.AlignHCenter)

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
        self.back_btn = QPushButton("← Back to USB")
        self.back_btn.setMinimumHeight(45)
        self.back_btn.setMinimumWidth(250)
        self.back_btn.setMaximumWidth(250)
        self.back_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.back_btn.setStyleSheet("""
            QPushButton {
                background-color: #804d4d;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 16px;
                font-weight: bold;
                padding: 12px 24px;
            }
            QPushButton:hover {
                background-color: #905d5d;
            }
        """)
        self.back_btn.clicked.connect(self.go_back)
        self.continue_btn = QPushButton("Set Print Options →")
        self.continue_btn.setMinimumHeight(45)
        self.continue_btn.setMinimumWidth(250)
        self.continue_btn.setMaximumWidth(250)
        self.continue_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
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
        self.continue_btn.clicked.connect(self.continue_to_print_options)
        bottom_controls.addWidget(self.back_btn)
        bottom_controls.addStretch()
        bottom_controls.addWidget(self.page_info)
        bottom_controls.addWidget(self.selected_count_label)
        bottom_controls.addStretch()
        bottom_controls.addWidget(self.continue_btn)

        right_layout.addLayout(preview_header_layout)
        right_layout.addWidget(self.preview_scroll)
        right_layout.addWidget(self.single_page_widget)
        right_layout.addLayout(bottom_controls)
        content_layout.addWidget(left_panel)
        content_layout.addWidget(right_panel)
        main_layout.addWidget(header_frame)
        main_layout.addLayout(content_layout)
        self.setLayout(main_layout)
        self.single_page_widget.hide()

    def _set_view_mode_buttons_style(self):
        pass

    def update_view_mode_buttons(self):
        self.view_all_btn.setChecked(self.view_mode == 'all')
        self.view_single_btn.setChecked(self.view_mode == 'single')

    def set_all_pages_view(self):
        self.view_mode = 'all'
        self.update_view_mode_buttons()
        self.show_pdf_preview()

    def set_single_page_view(self):
        self.view_mode = 'single'
        self.update_view_mode_buttons()
        if self.selected_pdf:
            if not (1 <= self.single_page_index <= self.selected_pdf['pages']):
                self.single_page_index = 1
        self.show_single_page()

    def show_single_page(self):
        self.preview_scroll.hide()
        self.single_page_widget.show()
        if not self.selected_pdf:
            return
        
        # Enable borderless mode for single page view
        self.single_page_preview.setBorderless(True)
        
        total_pages = self.selected_pdf['pages']
        if not (1 <= self.single_page_index <= total_pages):
            self.single_page_index = 1
        
        page_num = self.single_page_index
        self.page_info.setText(f"Page {page_num} of {total_pages}")
        self.page_input.setText(f"{page_num}")
        
        self.single_page_checkbox.blockSignals(True)
        self.single_page_checkbox.setChecked(self.selected_pages.get(page_num, False))
        self.single_page_checkbox.blockSignals(False)
        
        # Update zoom label
        self.update_zoom_label()
        
        self.single_page_preview.clear()

        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(self.selected_pdf['path'])
                if page_num <= len(doc):
                    page = doc[page_num-1]
                    
                    # Increase DPI for better quality in borderless mode
                    dpi = 300  # Higher DPI for better quality when zooming
                    scale = dpi / 72.0
                    
                    # Create transformation matrix
                    mat = fitz.Matrix(scale, scale)
                    
                    # Render the page
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    
                    # Convert to QImage and QPixmap
                    qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg)
                    
                    # The enhanced PDFPreviewWidget will handle scaling and zooming
                    self.single_page_preview.setPixmap(pixmap)
                    
                doc.close()
            except Exception as e:
                print(f"Error rendering page {page_num}: {e}")
                self.single_page_preview.clear()
        else:
            self.single_page_preview.clear()

    def show_pdf_preview(self):
        self.preview_scroll.show()
        self.single_page_widget.hide()
        if not self.selected_pdf:
            return
        
        # Disable borderless mode for all pages view (restore borders)
        self.single_page_preview.setBorderless(False)
        
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
            checked = self.selected_pages.get(page_num, True)
            page_widget = PDFPageWidget(page_num, checked=checked)
            page_widget.page_selected.connect(self.on_page_widget_clicked)
            page_widget.page_checkbox_clicked.connect(self.on_page_selected)
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
            self.preview_thread = PDFPreviewThread(pdf_path, max_preview_pages)
            self.preview_thread.preview_ready.connect(self.on_preview_ready)
            self.preview_thread.error_occurred.connect(self.on_preview_error)
            self.preview_thread.start()
        else:
            for widget in self.page_widgets:
                widget.preview_label.setText(f"Page {widget.page_num}\n\nPDF Preview\nRequires PyMuPDF")

    def prev_single_page(self):
        if self.single_page_index > 1:
            self.single_page_index -= 1
            self.show_single_page()

    def next_single_page(self):
        if self.selected_pdf and self.single_page_index < self.selected_pdf['pages']:
            self.single_page_index += 1
            self.show_single_page()

    def single_page_checkbox_changed(self, state):
        if self.selected_pdf:
            self.selected_pages[self.single_page_index] = (state == Qt.Checked)
            self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
            self.update_selected_count()

    def on_page_widget_clicked(self, page_num):
        self.single_page_index = page_num
        self.set_single_page_view()

    def on_page_selected(self, page_num, selected):
        self.selected_pages[page_num] = selected
        if self.selected_pdf:
            self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        self.update_selected_count()
        if self.view_mode == 'single' and page_num == self.single_page_index:
            self.single_page_checkbox.blockSignals(True)
            self.single_page_checkbox.setChecked(selected)
            self.single_page_checkbox.blockSignals(False)

    def load_pdf_files(self, pdf_files):
        self.pdf_files_data = []
        self.pdf_page_selections = {}
        for pdf_info in pdf_files:
            pdf_data = {
                'filename': pdf_info['filename'],
                'type': 'pdf',
                'pages': pdf_info.get('pages', 1),
                'size': pdf_info['size'],
                'path': pdf_info['path']
            }
            self.pdf_files_data.append(pdf_data)
        self.file_header.setText(f"PDF Files ({len(self.pdf_files_data)} files)")
        self.clear_file_list()
        self.pdf_buttons = []
        for pdf_data in self.pdf_files_data:
            pdf_btn = PDFButton(pdf_data)
            pdf_btn.pdf_selected.connect(self.select_pdf)
            self.pdf_buttons.append(pdf_btn)
            self.file_list_layout.insertWidget(self.file_list_layout.count() - 1, pdf_btn)
        self.selected_pdf = None
        self.selected_pages = None
        self.clear_preview()
        self.page_info.setText("Select a PDF to preview pages")
        self.preview_header.setText("Select a PDF file to preview pages")
        if self.pdf_files_data:
            self.select_pdf(self.pdf_files_data[0])

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
        if self.selected_pdf is not None and self.selected_pages is not None:
            self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        self.selected_pdf = pdf_data
        if pdf_data['path'] in self.pdf_page_selections:
            self.selected_pages = self.pdf_page_selections[pdf_data['path']].copy()
        else:
            self.selected_pages = {i: True for i in range(1, pdf_data['pages'] + 1)}
        for btn in self.pdf_buttons:
            btn.set_selected(btn.pdf_data == pdf_data)
        self.preview_header.setText(f"{pdf_data['filename']}")
        self.view_mode = 'all'
        self.update_view_mode_buttons()
        self.show_pdf_preview()
        self.single_page_index = 1

    def update_selected_count(self):
        if not self.selected_pages:
            return
        selected_count = sum(1 for selected in self.selected_pages.values() if selected)
        total_pages = len(self.selected_pages)
        self.selected_count_label.setText(f"Selected: {selected_count}/{total_pages} pages")
        self.continue_btn.setEnabled(selected_count > 0)

    def select_all_pages(self):
        if not self.selected_pages:
            return
        for page_num in self.selected_pages:
            self.selected_pages[page_num] = True
        if self.selected_pdf:
            self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        for widget in self.page_widgets:
            widget.checkbox.setChecked(True)
        self.update_selected_count()
        if self.view_mode == 'single':
            self.single_page_checkbox.blockSignals(True)
            self.single_page_checkbox.setChecked(True)
            self.single_page_checkbox.blockSignals(False)

    def deselect_all_pages(self):
        if not self.selected_pages:
            return
        for page_num in self.selected_pages:
            self.selected_pages[page_num] = False
        if self.selected_pdf:
            self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        for widget in self.page_widgets:
            widget.checkbox.setChecked(False)
        self.update_selected_count()
        if self.view_mode == 'single':
            self.single_page_checkbox.blockSignals(True)
            self.single_page_checkbox.setChecked(False)
            self.single_page_checkbox.blockSignals(False)

    def continue_to_print_options(self):
        """
        Gathers selected PDF and page data and transitions
        to the Print Options screen.
        """
        if not self.selected_pdf:
            QMessageBox.warning(self, "No PDF Selected", "Please select a PDF file.")
            return

        # Get a list of the page numbers the user has checked
        selected_pages_list = [page for page, selected in self.selected_pages.items() if selected]

        if not selected_pages_list:
            QMessageBox.warning(self, "No Pages Selected", "Please select at least one page to print.")
            return

        print("DEBUG: Transitioning to Print Options screen...")
        print(f"DEBUG: PDF: {self.selected_pdf['filename']}, Pages: {selected_pages_list}")

        # Get the single, existing print options screen instance from the main app
        options_screen = self.main_app.printing_options_screen

        # Call the method on that screen to pass the data it needs
        options_screen.set_pdf_data(self.selected_pdf, selected_pages_list)

        # Tell the main app to switch screens
        self.main_app.show_screen('printing_options')

    def on_preview_ready(self, page_num, pixmap):
        if self.view_mode == 'all' and page_num <= len(self.page_widgets):
            widget = self.page_widgets[page_num - 1]
            widget.set_preview_image(pixmap)
        elif self.view_mode == 'single' and page_num == self.single_page_index:
            self.single_page_preview.setPixmap(pixmap)

    def on_preview_error(self, page_num, error_msg):
        if self.view_mode == 'all' and page_num <= len(self.page_widgets):
            widget = self.page_widgets[page_num - 1]
            widget.set_error_message(error_msg)
        elif self.view_mode == 'single' and page_num == self.single_page_index:
            self.single_page_preview.clear()

    def go_back(self):
        self.main_app.show_screen('usb')

    def on_enter(self):
        if self.restore_payment_data:
            self.restore_payment_data = None
        elif self.pdf_files_data and not self.selected_pdf:
            self.select_pdf(self.pdf_files_data[0])

    def on_leave(self):
        if self.preview_thread and self.preview_thread.isRunning():
            self.preview_thread.stop()
            self.preview_thread.wait()

    def zoom_in(self):
        """Zoom in on the current page"""
        if self.single_page_preview:
            self.single_page_preview.zoomIn()
            self.update_zoom_label()

    def zoom_out(self):
        """Zoom out on the current page"""
        if self.single_page_preview:
            self.single_page_preview.zoomOut()
            self.update_zoom_label()

    def zoom_reset(self):
        """Reset zoom to fit the widget"""
        if self.single_page_preview:
            self.single_page_preview.resetZoom()
            self.update_zoom_label()

    def update_zoom_label(self):
        """Update the zoom percentage label"""
        if self.single_page_preview:
            zoom_factor = self.single_page_preview.getZoomFactor()
            percentage = int(zoom_factor * 100)
            self.zoom_label.setText(f"{percentage}%")