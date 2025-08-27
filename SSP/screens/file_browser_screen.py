import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QScrollArea,
    QFrame, QMessageBox, QGridLayout, QCheckBox, QSizePolicy, QStackedLayout, QSpacerItem
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

def get_base_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

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
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet(self.get_normal_style())
        self.clicked.connect(self.on_click)
        self.setMinimumWidth(300)
        self.setFixedHeight(60)

    def get_normal_style(self):
        return """
            QPushButton {
                background-color: #1e440a; color: #fff; border: 1px solid #555;
                border-radius: 8px; padding: 10px; text-align: left;
                font-size: 13px; margin: 2px; height: 60px;
            }
            QPushButton:hover { background-color: #2a5d1a; border: 1px solid #36454F; }
        """

    def get_selected_style(self):
        return """
            QPushButton {
                background-color: #4d80cc; color: #fff; border: 3px solid #6699ff;
                border-radius: 8px; padding: 10px; text-align: left;
                font-size: 13px; font-weight: bold; margin: 2px; height: 60px;
            }
        """

    def on_click(self): self.pdf_selected.emit(self.pdf_data)
    def set_selected(self, selected):
        self.is_selected = selected
        if selected: self.setStyleSheet(self.get_selected_style())
        else: self.setStyleSheet(self.get_normal_style())

class PDFPageWidget(QFrame):
    page_selected = pyqtSignal(int)
    page_checkbox_clicked = pyqtSignal(int, bool)
    def __init__(self, page_num=1, checked=True):
        super().__init__()
        self.page_num = page_num
        self.setFixedSize(180, 260)
        self.setup_ui(checked)
    def setup_ui(self, checked):
        self.setStyleSheet("QFrame { background-color: white; border: 2px solid #ddd; border-radius: 8px; margin: 5px; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        self.checkbox = QCheckBox(f"Page {self.page_num}")
        self.checkbox.setChecked(checked)
        self.checkbox.setStyleSheet("""
            QCheckBox { color: #36454F; font-size: 14px; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QCheckBox::indicator:checked { background-color: #4CAF50; border: 2px solid #4CAF50; }
            QCheckBox::indicator:unchecked { background-color: white; border: 2px solid #ccc; }
        """)
        self.checkbox.clicked.connect(self.on_checkbox_clicked)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setStyleSheet("QLabel { background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 4px; color: #36454F; font-size: 10px; }")
        self.preview_label.setText(f"Loading\nPage {self.page_num}...")
        layout.addWidget(self.checkbox)
        layout.addWidget(self.preview_label)
        self.setMouseTracking(True)
    def mousePressEvent(self, event):
        if not self.checkbox.geometry().contains(event.pos()): self.page_selected.emit(self.page_num)
    def on_checkbox_clicked(self, checked):
        self.page_checkbox_clicked.emit(self.page_num, checked)
        if checked: self.setStyleSheet("QFrame { background-color: white; border: 3px solid #4CAF50; border-radius: 8px; margin: 5px; }")
        else: self.setStyleSheet("QFrame { background-color: #f5f5f5; border: 2px solid #ccc; border-radius: 8px; margin: 5px; }")
    def set_preview_image(self, pixmap):
        self.preview_label.clear(); self.preview_label.setAlignment(Qt.AlignCenter); self.preview_label.setPixmap(pixmap)
    def set_error_message(self, error_msg):
        self.preview_label.setText(f"Page {self.page_num}\n\nError:\n{error_msg}")
        self.preview_label.setStyleSheet("QLabel { background-color: #ffeeee; border: 1px solid #ffaaaa; border-radius: 4px; color: #cc0000; font-size: 9px; }")

class PDFPreviewThread(QThread):
    preview_ready = pyqtSignal(int, QPixmap)
    error_occurred = pyqtSignal(int, str)
    def __init__(self, pdf_path, pages_to_render: list):
        super().__init__(); self.pdf_path = pdf_path; self.pages_to_render = pages_to_render; self.running = True
    def run(self):
        if not PYMUPDF_AVAILABLE:
            for page_num in self.pages_to_render:
                if not self.running: break
                self.error_occurred.emit(page_num, "PyMuPDF not available")
            return
        try:
            doc = fitz.open(self.pdf_path)
            for page_num in self.pages_to_render:
                if not self.running: break
                try:
                    page = doc[page_num - 1]
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
                    qimg = QImage.fromData(pix.tobytes("ppm"))
                    pixmap = QPixmap.fromImage(qimg).scaled(160, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    self.preview_ready.emit(page_num, pixmap)
                except Exception as e: self.error_occurred.emit(page_num, str(e))
            doc.close()
        except Exception as e:
            err_page = self.pages_to_render[0] if self.pages_to_render else 1
            self.error_occurred.emit(err_page, f"Failed to open PDF: {str(e)}")
    def stop(self): self.running = False

class FileBrowserScreen(QWidget):
    SINGLE_PAGE_PREVIEW_WIDTH = 360
    SINGLE_PAGE_PREVIEW_HEIGHT = 460
    ITEMS_PER_GRID_PAGE = 8

    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        try: self.usb_manager = main_app.usb_screen.usb_manager
        except Exception: self.usb_manager = USBFileManager()
        self.pdf_files_data = []; self.selected_pdf = None; self.pdf_buttons = []
        self.page_widgets = []; self.page_widget_map = {}; self.selected_pages = None
        self.pdf_page_selections = {}; self.preview_thread = None; self.restore_payment_data = None
        self.view_mode = 'all'; self.single_page_index = 1; self.current_grid_page = 1
        self.setup_ui()

    def setup_ui(self):
        stacked_layout = QStackedLayout()
        stacked_layout.setContentsMargins(0, 0, 0, 0)
        stacked_layout.setStackingMode(QStackedLayout.StackAll)

        background_label = QLabel()
        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'file_browser_screen background.png')
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            background_label.setPixmap(pixmap)
            background_label.setScaledContents(True)
        else:
            background_label.setStyleSheet("background-color: #1f1f38;")

        foreground_widget = QWidget()
        foreground_widget.setStyleSheet("background-color: transparent;")
        main_col = QVBoxLayout(foreground_widget)
        main_col.setContentsMargins(0, 0, 0, 0)
        main_col.setSpacing(0)

        # ---- MAIN SPLIT: LEFT (file list), RIGHT (preview) ----
        split_row = QHBoxLayout()
        split_row.setContentsMargins(0, 0, 0, 0)
        split_row.setSpacing(0)

        # LEFT PANEL
        left_panel = QFrame()
        left_panel.setFixedWidth(360)
        left_panel.setStyleSheet("QFrame { background-color: transparent; border: none; }")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 0, 10, 20)
        left_layout.setSpacing(10) # between pdf files # and files
        left_layout.addSpacing(94)  # Adjust this value to bring the label lower or higher
        self.file_header = QLabel("PDF Files (0 files)")
        self.file_header.setStyleSheet("QLabel { color: #36454F; font-size: 16px; font-weight: bold; background-color: transparent; padding-left: 13px;  /* Move text right by x px */}")
        self.file_header.setFixedHeight(32)
        left_layout.addWidget(self.file_header, 0, Qt.AlignLeft)
        file_scroll = QScrollArea()
        file_scroll.setWidgetResizable(True)
        file_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        file_scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical { background-color: #333; width: 12px; border-radius: 6px; }
            QScrollBar::handle:vertical { background-color: #666; border-radius: 6px; min-height: 20px; }
        """)
        self.file_list_widget = QWidget()
        self.file_list_widget.setStyleSheet("background-color: transparent;")
        self.file_list_layout = QVBoxLayout(self.file_list_widget)
        self.file_list_layout.setSpacing(6)
        self.file_list_layout.addStretch()
        file_scroll.setWidget(self.file_list_widget)
        left_layout.addWidget(file_scroll)
        split_row.addWidget(left_panel, 0)

        # RIGHT PANEL
        right_panel = QFrame()
        right_panel.setStyleSheet("background-color: transparent;")
        right_panel_layout = QVBoxLayout(right_panel)
        right_panel_layout.setContentsMargins(0, 0, 20, 12)
        right_panel_layout.setSpacing(0)

        right_panel_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Expanding))

        header_row = QHBoxLayout()
        header_row.setSpacing(10)
        header_row.setContentsMargins(20, 0, 20, 0)

        self.preview_header = QLabel("Select a PDF file to preview pages")
        self.preview_header.setStyleSheet("QLabel { color: #36454F; font-size: 18px; font-weight: bold; background-color: transparent; }")
        self.preview_header.setFixedHeight(32)
        button_height = 40

        # --- BUTTON STYLES ---
        all_button_style = f"""
            QPushButton {{
                color: white; font-size: 12px; font-weight: bold;
                border: none; border-radius: 4px !important; height: {button_height}px;
                background-color: #1e440a;
                padding-left: 12px; padding-right: 12px;
            }}
            QPushButton:checked, QPushButton:hover {{ background-color: #2a5d1a; }}
        """

        # -- Apply styles to main action buttons --
        self.view_all_btn = QPushButton("All Pages View")
        self.view_single_btn = QPushButton("Single Page View")
        self.view_all_btn.setCheckable(True)
        self.view_single_btn.setCheckable(True)
        self.view_all_btn.setChecked(True)
        self.view_all_btn.setStyleSheet(all_button_style)
        self.view_single_btn.setStyleSheet(all_button_style)
        self.view_all_btn.setFixedHeight(button_height)
        self.view_single_btn.setFixedHeight(button_height)
        self.view_all_btn.clicked.connect(self.set_all_pages_view)
        self.view_single_btn.clicked.connect(self.set_single_page_view)

        self.select_all_btn = QPushButton("Select All Pages")
        self.select_all_btn.setVisible(False)
        self.select_all_btn.setStyleSheet(all_button_style)
        self.select_all_btn.setFixedHeight(button_height)
        self.select_all_btn.clicked.connect(self.select_all_pages)

        # --- Deselect All: LEAVE AS IS ---
        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setVisible(False)
        self.deselect_all_btn.setStyleSheet("""
            QPushButton {
                color: white; font-size: 12px; font-weight: bold;
                border: none; border-radius: 4px; height: 40px;
                background-color: #ff9800;
                padding-left: 12px; padding-right: 12px;
            }
            QPushButton:hover, QPushButton:checked { background-color: #f57c00; }
        """)
        self.deselect_all_btn.setFixedHeight(button_height)
        self.deselect_all_btn.clicked.connect(self.deselect_all_pages)

        header_row.addWidget(self.preview_header, 1, Qt.AlignLeft)
        header_row.addWidget(self.view_all_btn)
        header_row.addWidget(self.view_single_btn)
        header_row.addWidget(self.select_all_btn)
        header_row.addWidget(self.deselect_all_btn)
        right_panel_layout.addLayout(header_row)
        right_panel_layout.addSpacing(25)

        # === CHANGED: set background-color of preview container ===
        self.preview_container = QFrame()
        self.preview_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.preview_container.setStyleSheet(
            "QFrame { border: 2px solid #0f1f00; border-radius: 6px; background-color: #fffff; }"
        )
        self.preview_container.setFixedSize(800, 560)
        self.preview_layout = QGridLayout(self.preview_container)
        self.preview_layout.setSpacing(10)
        self.preview_layout.setAlignment(Qt.AlignTop)

        # === SINGLE PAGE VIEW CONTAINER ===
        self.single_page_widget = QWidget()
        self.single_page_widget.setStyleSheet("background-color: #fffdf7;")  # CHANGED
        self.single_page_layout = QVBoxLayout(self.single_page_widget)
        self.single_page_layout.setSpacing(8)
        self.single_page_layout.setAlignment(Qt.AlignVCenter)
        self.single_page_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        nav_layout = QHBoxLayout()
        nav_btn_style = f"""
            QPushButton {{
                background-color: #1e440a; color: #fff; border: none; border-radius: 4px;
                font-size: 18px; width: 40px; height: 40px; min-width: 40px; max-width: 40px; min-height: 40px; max-height: 40px;
                padding: 0; font-weight: bold;
            }}
            QPushButton:pressed, QPushButton:checked, QPushButton:hover {{ background-color: #2a5d1a; }}
        """
        self.prev_page_btn = QPushButton("←"); self.prev_page_btn.setStyleSheet(nav_btn_style)
        self.next_page_btn = QPushButton("→"); self.next_page_btn.setStyleSheet(nav_btn_style)
        self.prev_page_btn.setFixedHeight(button_height)
        self.next_page_btn.setFixedHeight(button_height)
        # === CHANGED: page number and zoom labels, transparent bg and bold text ===
        self.page_input = QLabel("1")
        self.page_input.setStyleSheet(
            "QLabel { background-color: transparent; color: #36454F; font-size: 13px; min-width: 40px; max-width: 40px; border-radius: 3px; padding: 1px 4px; border: none; font-weight: bold; qproperty-alignment: AlignCenter; }"
        )
        zoom_btn_style = nav_btn_style
        self.zoom_in_btn = QPushButton("+"); self.zoom_in_btn.setStyleSheet(zoom_btn_style); self.zoom_in_btn.setFixedHeight(button_height)
        self.zoom_out_btn = QPushButton("−"); self.zoom_out_btn.setStyleSheet(zoom_btn_style); self.zoom_out_btn.setFixedHeight(button_height)
        self.zoom_reset_btn = QPushButton("⌂"); self.zoom_reset_btn.setStyleSheet(zoom_btn_style); self.zoom_reset_btn.setFixedHeight(button_height)
        # === CHANGED: zoom label, transparent bg and bold text ===
        self.zoom_label = QLabel("100%")
        self.zoom_label.setStyleSheet(
            "QLabel { background-color: transparent; color: #36454F; font-size: 12px; min-width: 45px; max-width: 45px; border-radius: 3px; padding: 2px 4px; border: none; font-weight: bold; qproperty-alignment: AlignCenter; margin: 0 5px; }"
        )
        nav_layout.addWidget(self.prev_page_btn)
        nav_layout.addWidget(self.page_input)
        nav_layout.addWidget(self.next_page_btn)
        nav_layout.addStretch()
        zoom_label_container = QLabel("Zoom:")
        zoom_label_container.setStyleSheet("background-color: transparent; color: #36454F; font-weight: bold;")
        nav_layout.addWidget(zoom_label_container)
        nav_layout.addWidget(self.zoom_out_btn)
        nav_layout.addWidget(self.zoom_label)
        nav_layout.addWidget(self.zoom_in_btn)
        nav_layout.addWidget(self.zoom_reset_btn)
        self.prev_page_btn.clicked.connect(self.prev_single_page); self.next_page_btn.clicked.connect(self.next_single_page)
        self.zoom_in_btn.clicked.connect(self.zoom_in); self.zoom_out_btn.clicked.connect(self.zoom_out); self.zoom_reset_btn.clicked.connect(self.zoom_reset)
        self.single_page_layout.addLayout(nav_layout)
        self.single_page_checkbox = QCheckBox("Select this page")
        self.single_page_checkbox.setStyleSheet("QCheckBox { color: #36454F; font-size: 13px; background-color: transparent; }")
        self.single_page_checkbox.stateChanged.connect(self.single_page_checkbox_changed)
        self.single_page_layout.addWidget(self.single_page_checkbox)
        self.single_page_preview = PDFPreviewWidget()
        self.single_page_preview.setFixedSize(self.SINGLE_PAGE_PREVIEW_WIDTH, self.SINGLE_PAGE_PREVIEW_HEIGHT)
        self.single_page_preview.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.single_page_layout.addWidget(self.single_page_preview, 0, Qt.AlignHCenter)

        # Pagination Controls
        self.prev_grid_page_btn = QPushButton("<< Prev")
        self.next_grid_page_btn = QPushButton("Next >>")
        pagination_style = f"""
            QPushButton {{
                color: white; font-size: 12px; font-weight: bold;
                border: none; border-radius: 4px; height: {button_height}px;
                background-color: #1e440a;
                padding-left: 12px; padding-right: 12px;
            }}
            QPushButton:hover, QPushButton:checked {{ background-color: #2a5d1a; }}
            QPushButton:disabled {{ background-color: #3e423a; color: #555; }}
        """
        self.prev_grid_page_btn.setStyleSheet(pagination_style)
        self.next_grid_page_btn.setStyleSheet(pagination_style)
        self.prev_grid_page_btn.setFixedHeight(button_height)
        self.next_grid_page_btn.setFixedHeight(button_height)
        self.prev_grid_page_btn.clicked.connect(self.prev_grid_page)
        self.next_grid_page_btn.clicked.connect(self.next_grid_page)
        self.grid_page_label = QLabel("Page 1 / 1")
        self.grid_page_label.setAlignment(Qt.AlignCenter)
        self.grid_page_label.setStyleSheet("color: #36454F; font-size: 14px; background-color: transparent;")

        bottom_controls = QHBoxLayout()
        bottom_controls.setSpacing(15)
        # --- Back to USB: LEAVE AS IS ---
        self.back_btn = QPushButton("← Back to USB")
        self.back_btn.setStyleSheet(f"""
            QPushButton {{
                color: white; font-size: 12px; font-weight: bold;
                border: none; border-radius: 4px; height: {button_height}px;
                background-color: #ff0000;
                padding-left: 12px; padding-right: 12px;
            }}
            QPushButton:hover {{ background-color: #ffb84d; }}
        """)
        self.back_btn.setFixedHeight(button_height)
        self.back_btn.clicked.connect(self.go_back)
        # Continue Button: Use main style
        self.continue_btn = QPushButton("Set Print Options →")
        self.continue_btn.setStyleSheet(all_button_style)
        self.continue_btn.setFixedHeight(button_height)
        self.continue_btn.clicked.connect(self.continue_to_print_options)
        self.continue_btn.setVisible(False)

        self.page_info = QLabel("No PDF selected")
        self.page_info.setStyleSheet("QLabel { color: #36454F; font-size: 14px; background-color: transparent; }")
        self.selected_count_label = QLabel("")
        self.selected_count_label.setStyleSheet("QLabel { color: #4CAF50; font-size: 14px; font-weight: bold; background-color: transparent; }")

        pagination_controls = QHBoxLayout()
        pagination_controls.setSpacing(6)
        pagination_controls.addWidget(self.prev_grid_page_btn, 0, Qt.AlignCenter)
        pagination_controls.addWidget(self.grid_page_label, 0, Qt.AlignCenter)
        pagination_controls.addWidget(self.next_grid_page_btn, 0, Qt.AlignCenter)

        bottom_controls.addWidget(self.back_btn, 0, Qt.AlignCenter)
        bottom_controls.addStretch(1)
        bottom_controls.addLayout(pagination_controls)
        bottom_controls.addStretch(1)
        bottom_controls.addWidget(self.page_info, 0, Qt.AlignCenter)
        bottom_controls.addWidget(self.selected_count_label, 0, Qt.AlignCenter)
        bottom_controls.addStretch(1)
        bottom_controls.addWidget(self.continue_btn, 0, Qt.AlignCenter)

        preview_area_layout = QStackedLayout()
        preview_area_layout.setStackingMode(QStackedLayout.StackAll)
        preview_area_layout.setContentsMargins(0, 0, 0, 0)
        preview_area_layout.addWidget(self.preview_container)
        preview_area_layout.addWidget(self.single_page_widget)
        self.single_page_widget.hide()

        right_panel_layout.addLayout(preview_area_layout)
        right_panel_layout.addSpacing(30)
        right_panel_layout.addLayout(bottom_controls)

        split_row.addWidget(right_panel, 1)
        main_col.addLayout(split_row, 1)

        stacked_layout.addWidget(background_label)
        stacked_layout.addWidget(foreground_widget)
        self.setLayout(stacked_layout)

        self.prev_grid_page_btn.hide(); self.grid_page_label.hide(); self.next_grid_page_btn.hide()

    # ---------- All your original methods below this line are unchanged ----------
    def show_pdf_preview(self):
        self.preview_container.show()
        self.single_page_widget.hide()
        self.prev_grid_page_btn.show(); self.grid_page_label.show(); self.next_grid_page_btn.show()
        if not self.selected_pdf:
            self.prev_grid_page_btn.hide(); self.grid_page_label.hide(); self.next_grid_page_btn.hide()
            return
        self.clear_preview()
        total_doc_pages = self.selected_pdf['pages']
        self.page_info.setText(""); self.update_selected_count()
        self.select_all_btn.setVisible(True); self.deselect_all_btn.setVisible(True); self.continue_btn.setVisible(True)
        total_grid_pages = (total_doc_pages + self.ITEMS_PER_GRID_PAGE - 1) // self.ITEMS_PER_GRID_PAGE
        self.grid_page_label.setText(f"{self.current_grid_page} / {total_grid_pages}")
        self.prev_grid_page_btn.setEnabled(self.current_grid_page > 1); self.next_grid_page_btn.setEnabled(self.current_grid_page < total_grid_pages)
        start_page = (self.current_grid_page - 1) * self.ITEMS_PER_GRID_PAGE + 1
        end_page = min(self.current_grid_page * self.ITEMS_PER_GRID_PAGE, total_doc_pages)
        pages_to_show = list(range(start_page, end_page + 1))
        for i, page_num in enumerate(pages_to_show):
            page_widget = PDFPageWidget(page_num, checked=self.selected_pages.get(page_num, True))
            page_widget.page_selected.connect(self.on_page_widget_clicked); page_widget.page_checkbox_clicked.connect(self.on_page_selected)
            self.page_widgets.append(page_widget); self.page_widget_map[page_num] = page_widget
            self.preview_layout.addWidget(page_widget, i // 4, i % 4)
        if PYMUPDF_AVAILABLE:
            self.preview_thread = PDFPreviewThread(self.selected_pdf['path'], pages_to_show)
            self.preview_thread.preview_ready.connect(self.on_preview_ready); self.preview_thread.error_occurred.connect(self.on_preview_error)
            self.preview_thread.start()
        else:
            for widget in self.page_widgets: widget.preview_label.setText(f"Page {widget.page_num}\n\nPDF Preview\nRequires PyMuPDF")

    def show_single_page(self):
        self.preview_container.hide()
        self.single_page_widget.show()
        self.prev_grid_page_btn.hide(); self.grid_page_label.hide(); self.next_grid_page_btn.hide()
        if not self.selected_pdf: return
        self.single_page_preview.setBorderless(True)
        total_pages = self.selected_pdf['pages']
        if not (1 <= self.single_page_index <= total_pages): self.single_page_index = 1
        page_num = self.single_page_index; self.page_info.setText(f"Page {page_num} of {total_pages}"); self.page_input.setText(f"{page_num}")
        self.single_page_checkbox.blockSignals(True); self.single_page_checkbox.setChecked(self.selected_pages.get(page_num, False)); self.single_page_checkbox.blockSignals(False)
        self.update_zoom_label(); self.single_page_preview.clear()
        if PYMUPDF_AVAILABLE:
            try:
                doc = fitz.open(self.selected_pdf['path'])
                if page_num <= len(doc):
                    page = doc[page_num-1]
                    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72), alpha=False)
                    qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
                    self.single_page_preview.setPixmap(QPixmap.fromImage(qimg))
                doc.close()
            except Exception as e: print(f"Error rendering page {page_num}: {e}"); self.single_page_preview.clear()
        else: self.single_page_preview.clear()

    def _set_view_mode_buttons_style(self): pass
    def update_view_mode_buttons(self): self.view_all_btn.setChecked(self.view_mode == 'all'); self.view_single_btn.setChecked(self.view_mode == 'single')
    def set_all_pages_view(self): self.view_mode = 'all'; self.update_view_mode_buttons(); self.show_pdf_preview()
    def set_single_page_view(self):
        self.view_mode = 'single'; self.update_view_mode_buttons()
        if self.selected_pdf and not (1 <= self.single_page_index <= self.selected_pdf['pages']): self.single_page_index = 1
        self.show_single_page()
    def prev_grid_page(self):
        if self.current_grid_page > 1: self.current_grid_page -= 1; self.show_pdf_preview()
    def next_grid_page(self):
        if not self.selected_pdf: return
        total_doc_pages = self.selected_pdf['pages']
        total_grid_pages = (total_doc_pages + self.ITEMS_PER_GRID_PAGE - 1) // self.ITEMS_PER_GRID_PAGE
        if self.current_grid_page < total_grid_pages: self.current_grid_page += 1; self.show_pdf_preview()
    def prev_single_page(self):
        if self.single_page_index > 1: self.single_page_index -= 1; self.show_single_page()
    def next_single_page(self):
        if self.selected_pdf and self.single_page_index < self.selected_pdf['pages']: self.single_page_index += 1; self.show_single_page()
    def single_page_checkbox_changed(self, state):
        if self.selected_pdf: self.selected_pages[self.single_page_index] = (state == Qt.Checked); self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy(); self.update_selected_count()
    def on_page_widget_clicked(self, page_num): self.single_page_index = page_num; self.set_single_page_view()
    def on_page_selected(self, page_num, selected):
        self.selected_pages[page_num] = selected
        if self.selected_pdf: self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        self.update_selected_count()
        if self.view_mode == 'single' and page_num == self.single_page_index:
            self.single_page_checkbox.blockSignals(True); self.single_page_checkbox.setChecked(selected); self.single_page_checkbox.blockSignals(False)
    def load_pdf_files(self, pdf_files):
        self.pdf_files_data = []
        self.pdf_page_selections = {}
        for pdf_info in pdf_files: self.pdf_files_data.append({'filename': pdf_info['filename'], 'type': 'pdf', 'pages': pdf_info.get('pages', 1), 'size': pdf_info['size'], 'path': pdf_info['path']})
        self.file_header.setText(f"PDF Files ({len(self.pdf_files_data)} files)")
        self.clear_file_list()
        self.pdf_buttons = []
        for pdf_data in self.pdf_files_data:
            pdf_btn = PDFButton(pdf_data)
            pdf_btn.pdf_selected.connect(self.select_pdf)
            self.pdf_buttons.append(pdf_btn)
            self.file_list_layout.insertWidget(self.file_list_layout.count() - 1, pdf_btn)
        self.selected_pdf = None; self.selected_pages = None
        self.clear_preview()
        self.page_info.setText("Select a PDF to preview pages")
        self.preview_header.setText("Select a PDF file to preview pages")
        self.prev_grid_page_btn.hide(); self.grid_page_label.hide(); self.next_grid_page_btn.hide()
        if self.pdf_files_data: self.select_pdf(self.pdf_files_data[0])
    def clear_file_list(self):
        while self.file_list_layout.count() > 1:
            child = self.file_list_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
    def clear_preview(self):
        if self.preview_thread and self.preview_thread.isRunning(): self.preview_thread.stop(); self.preview_thread.wait()
        while self.preview_layout.count():
            child = self.preview_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.page_widgets.clear(); self.page_widget_map.clear()
        self.select_all_btn.setVisible(False); self.deselect_all_btn.setVisible(False); self.continue_btn.setVisible(False)
        self.selected_count_label.setText("")
    def select_pdf(self, pdf_data):
        if self.selected_pdf is not None and self.selected_pages is not None: self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        self.selected_pdf = pdf_data
        if pdf_data['path'] in self.pdf_page_selections: self.selected_pages = self.pdf_page_selections[self.selected_pdf['path']].copy()
        else: self.selected_pages = {i: True for i in range(1, pdf_data['pages'] + 1)}
        for btn in self.pdf_buttons: btn.set_selected(btn.pdf_data == pdf_data)
        self.preview_header.setText(f"{pdf_data['filename']}")
        self.view_mode = 'all'; self.update_view_mode_buttons()
        self.current_grid_page = 1; self.single_page_index = 1
        self.show_pdf_preview()
    def update_selected_count(self):
        if not self.selected_pages: return
        selected_count = sum(1 for selected in self.selected_pages.values() if selected)
        self.selected_count_label.setText(f"Selected: {selected_count}/{len(self.selected_pages)} pages")
        self.continue_btn.setEnabled(selected_count > 0)
    def select_all_pages(self):
        if not self.selected_pages: return
        for page_num in self.selected_pages: self.selected_pages[page_num] = True
        if self.selected_pdf: self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        for widget in self.page_widgets: widget.checkbox.setChecked(True)
        self.update_selected_count()
        if self.view_mode == 'single': self.single_page_checkbox.blockSignals(True); self.single_page_checkbox.setChecked(True); self.single_page_checkbox.blockSignals(False)
    def deselect_all_pages(self):
        if not self.selected_pages: return
        for page_num in self.selected_pages: self.selected_pages[page_num] = False
        if self.selected_pdf: self.pdf_page_selections[self.selected_pdf['path']] = self.selected_pages.copy()
        for widget in self.page_widgets: widget.checkbox.setChecked(False)
        self.update_selected_count()
        if self.view_mode == 'single': self.single_page_checkbox.blockSignals(True); self.single_page_checkbox.setChecked(False); self.single_page_checkbox.blockSignals(False)
    def continue_to_print_options(self):
        if not self.selected_pdf: QMessageBox.warning(self, "No PDF Selected", "Please select a PDF file."); return
        selected_pages_list = [page for page, selected in self.selected_pages.items() if selected]
        if not selected_pages_list: QMessageBox.warning(self, "No Pages Selected", "Please select at least one page to print."); return
        options_screen = self.main_app.printing_options_screen
        options_screen.set_pdf_data(self.selected_pdf, selected_pages_list)
        self.main_app.show_screen('printing_options')
    def on_preview_ready(self, page_num, pixmap):
        if self.view_mode == 'all':
            widget = self.page_widget_map.get(page_num)
            if widget: widget.set_preview_image(pixmap)
        elif self.view_mode == 'single' and page_num == self.single_page_index: self.single_page_preview.setPixmap(pixmap)
    def on_preview_error(self, page_num, error_msg):
        if self.view_mode == 'all':
            widget = self.page_widget_map.get(page_num)
            if widget: widget.set_error_message(error_msg)
        elif self.view_mode == 'single' and page_num == self.single_page_index: self.single_page_preview.clear()
    def go_back(self): self.main_app.show_screen('usb')
    def on_enter(self):
        if self.restore_payment_data: self.restore_payment_data = None
        elif self.pdf_files_data and not self.selected_pdf: self.select_pdf(self.pdf_files_data[0])
    def on_leave(self):
        if self.preview_thread and self.preview_thread.isRunning(): self.preview_thread.stop(); self.preview_thread.wait()
    def zoom_in(self):
        if self.single_page_preview: self.single_page_preview.zoomIn(); self.update_zoom_label()
    def zoom_out(self):
        if self.single_page_preview: self.single_page_preview.zoomOut(); self.update_zoom_label()
    def zoom_reset(self):
        if self.single_page_preview: self.single_page_preview.resetZoom(); self.update_zoom_label()
    def update_zoom_label(self):
        if self.single_page_preview:
            zoom_factor = self.single_page_preview.getZoomFactor()
            self.zoom_label.setText(f"{int(zoom_factor * 100)}%")