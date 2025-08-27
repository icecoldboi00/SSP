import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QMessageBox, QStackedLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap

import fitz
import cv2
import numpy as np
from typing import List, Dict

def get_base_dir():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

class PDFColorAnalyzer:
    def __init__(self, black_price: float, color_price: float):
        self.black_price = black_price
        self.color_price = color_price

    def is_page_black_only(self, page_image: np.ndarray,
                          color_tolerance: int = 15,
                          pixel_count_threshold: int = 200) -> bool:
        if page_image.size == 0: return True
        b, g, r = page_image[:, :, 0], page_image[:, :, 1], page_image[:, :, 2]
        channel_max = np.maximum(np.maximum(r, g), b)
        channel_min = np.minimum(np.minimum(r, g), b)
        color_diff = (channel_max - channel_min).astype(np.uint8)
        colored_pixel_count = np.count_nonzero(color_diff > color_tolerance)
        return colored_pixel_count < pixel_count_threshold

    def analyze_pdf_pages(self, pdf_path: str, pages_to_check: List[int], user_wants_color: bool, dpi: int = 150) -> Dict:
        results = {
            'page_analysis': {}, 
            'pricing': {'black_pages_count': 0, 'color_pages_count': 0, 'base_cost': 0},
            'error': None
        }
        try:
            pdf_document = fitz.open(pdf_path)
            for page_num_1_based in pages_to_check:
                page_num_0_based = page_num_1_based - 1
                if not (0 <= page_num_0_based < len(pdf_document)): continue

                page = pdf_document[page_num_0_based]
                mat = fitz.Matrix(dpi/72, dpi/72)
                pix = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csRGB)
                page_image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)

                is_black_only = self.is_page_black_only(page_image)
                
                page_price = 0 
                
                if user_wants_color and not is_black_only:
                    page_price = self.color_price
                    results['pricing']['color_pages_count'] += 1
                else:
                    page_price = self.black_price
                    results['pricing']['black_pages_count'] += 1
                
                results['pricing']['base_cost'] += page_price
                results['page_analysis'][page_num_1_based] = {'is_black_only': is_black_only, 'final_price': page_price}

            pdf_document.close()
            return results
        except Exception as e:
            results['error'] = f"Error processing PDF: {str(e)}"
            return results

class AnalysisThread(QThread):
    analysis_complete = pyqtSignal(dict)

    def __init__(self, analyzer, pdf_path, selected_pages, user_wants_color):
        super().__init__()
        self.analyzer = analyzer
        self.pdf_path = pdf_path
        self.selected_pages = selected_pages
        self.user_wants_color = user_wants_color
        self._is_running = True

    def run(self):
        if not self._is_running: return
        results = self.analyzer.analyze_pdf_pages(self.pdf_path, self.selected_pages, self.user_wants_color)
        if self._is_running:
            self.analysis_complete.emit(results)
    
    def stop(self):
        self._is_running = False

class Print_Options_Screen(QWidget):
    def __init__(self, main_app):
        super().__init__()
        self.main_app = main_app
        self.selected_pdf = None
        self.selected_pages = None

        self.analyzer = PDFColorAnalyzer(black_price=3.0, color_price=5.0)
        self.analysis_thread = None
        self.analysis_results = None

        self._copies = 1
        self._color_mode = "Black and White"

        self.setup_ui()

    def setup_ui(self):
        stacked_layout = QStackedLayout()
        stacked_layout.setContentsMargins(0, 0, 0, 0)
        stacked_layout.setStackingMode(QStackedLayout.StackAll)

        background_label = QLabel()
        base_dir = get_base_dir()
        image_path = os.path.join(base_dir, 'assets', 'print_options_screen background.png')
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            background_label.setPixmap(pixmap)
            background_label.setScaledContents(True)
        else:
            print(f"WARNING: Background image not found at '{image_path}'.")
            background_label.setStyleSheet("background-color: #1f1f38;")

        foreground_widget = QWidget()
        foreground_widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(foreground_widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(0)

        layout.addStretch(1)

        # === Centered Container for Color Mode and Number of Copies ===
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(24)
        center_layout.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)

        # ---- Number of Copies Row ----
        copies_row = QHBoxLayout()
        copies_row.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        copies_label = QLabel("Number of Copies:")
        copies_label.setStyleSheet("color: #36454F; font-size: 18px; font-weight: bold; background-color: transparent;")
        copies_row.addWidget(copies_label)

        copies_btn_style = """
            QPushButton {
                background-color: #1e440a; color: #fff; border: none; border-radius: 4px;
                font-size: 22px; width: 44px; height: 44px; min-width: 44px; max-width: 44px; min-height: 44px; max-height: 44px;
                padding: 0; font-weight: bold;
            }
            QPushButton:pressed, QPushButton:checked, QPushButton:hover { background-color: #2a5d1a; }
        """
        self.copies_minus_btn = QPushButton("−")
        self.copies_plus_btn = QPushButton("+")
        self.copies_minus_btn.setStyleSheet(copies_btn_style)
        self.copies_plus_btn.setStyleSheet(copies_btn_style)
        self.copies_minus_btn.setFixedSize(44, 44)
        self.copies_plus_btn.setFixedSize(44, 44)
        self.copies_minus_btn.clicked.connect(lambda: self.change_copies(-1))
        self.copies_plus_btn.clicked.connect(lambda: self.change_copies(1))
        copies_row.addSpacing(20)
        copies_row.addWidget(self.copies_minus_btn)

        self.copies_count_label = QLabel("1")
        self.copies_count_label.setStyleSheet(
            "QLabel { background-color: transparent; color: #36454F; font-size: 22px; min-width: 40px; max-width: 40px; border-radius: 3px; padding: 1px 4px; border: none; font-weight: bold; qproperty-alignment: AlignCenter; }"
        )
        self.copies_count_label.setAlignment(Qt.AlignCenter)
        copies_row.addWidget(self.copies_count_label)
        copies_row.addWidget(self.copies_plus_btn)
        # Remember the left position for alignment
        # To align the color buttons edge with the minus button, get the minus button's index
        # minus_button_edge_index = copies_row.indexOf(self.copies_minus_btn)
        # Now, add stretch at the end so the rightmost edge aligns.
        copies_row.addStretch(1)
        center_layout.addLayout(copies_row)

        # ---- Color Mode Row (Label left, Buttons right-aligned with minus button) ----
        color_row = QHBoxLayout()
        color_row.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        color_label = QLabel("Color Mode:")
        color_label.setStyleSheet("color: #36454F; font-size: 18px; font-weight: bold; background-color: transparent;")
        color_row.addWidget(color_label)
        color_row.addStretch(1)  # Push the buttons to the right edge

        color_btn_style = """
            QPushButton {
                color: white; font-size: 16px; font-weight: bold;
                border: none; border-radius: 4px !important; height: 44px; min-width: 130px;
                background-color: #1e440a;
                padding-left: 12px; padding-right: 12px;
            }
            QPushButton:checked, QPushButton:hover { background-color: #2a5d1a; }
        """
        self.bw_btn = QPushButton("Black and White")
        self.color_btn = QPushButton("Colored")
        self.bw_btn.setCheckable(True)
        self.color_btn.setCheckable(True)
        self.bw_btn.setStyleSheet(color_btn_style)
        self.color_btn.setStyleSheet(color_btn_style)
        self.bw_btn.setChecked(True)
        color_row.addWidget(self.bw_btn)
        color_row.addSpacing(8)
        color_row.addWidget(self.color_btn)
        center_layout.addLayout(color_row)

        # Add centered container to the main layout
        layout.addWidget(center_container, 0, Qt.AlignHCenter)

        # Add more space below the centered container before cost/details.
        layout.addSpacing(60)

        # ---- Cost and Details (placed lower and centered) ----
        self.cost_label = QLabel("Calculating cost...")
        self.cost_label.setAlignment(Qt.AlignCenter)
        self.cost_label.setStyleSheet("color: #33cc33; font-size: 24px; font-weight: bold; margin: 0px 0 0 0;")
        layout.addWidget(self.cost_label, 0, Qt.AlignHCenter)

        self.analysis_details_label = QLabel("Analysis details will appear here.")
        self.analysis_details_label.setAlignment(Qt.AlignCenter)
        self.analysis_details_label.setStyleSheet("color: #36454F; font-size: 14px; margin-top: 5px;")
        layout.addWidget(self.analysis_details_label, 0, Qt.AlignHCenter)

        layout.addStretch(2)

        # ---- Buttons ----
        buttons_layout = QHBoxLayout()
        back_btn = QPushButton("← Back to File Browser")
        back_btn.setMinimumHeight(50)
        back_btn.setStyleSheet("""
            QPushButton {
                color: white; font-size: 12px; font-weight: bold;
                border: none; border-radius: 4px; height: 40px;
                background-color: #ff0000;
                padding-left: 12px; padding-right: 12px;
            }
            QPushButton:hover { background-color: #ffb84d; }
        """)

        self.continue_btn = QPushButton("Continue to Payment →")
        self.continue_btn.setMinimumHeight(50)
        self.continue_btn.setStyleSheet("""
            QPushButton {
                color: white; font-size: 12px; font-weight: bold;
                border: none; border-radius: 4px !important; height: 40px;
                background-color: #1e440a;
                padding-left: 12px; padding-right: 12px;
            }
            QPushButton:checked, QPushButton:hover { background-color: #2a5d1a; }
        """)

        back_btn.clicked.connect(self.go_back)
        self.continue_btn.clicked.connect(self.continue_to_payment)

        buttons_layout.addWidget(back_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.continue_btn)
        layout.addLayout(buttons_layout)

        stacked_layout.addWidget(background_label)
        stacked_layout.addWidget(foreground_widget)
        self.setLayout(stacked_layout)

        self.bw_btn.clicked.connect(self.set_bw_mode)
        self.color_btn.clicked.connect(self.set_color_mode)

    def set_bw_mode(self):
        self._color_mode = "Black and White"
        self.bw_btn.setChecked(True)
        self.color_btn.setChecked(False)
        self.trigger_analysis()

    def set_color_mode(self):
        self._color_mode = "Color"
        self.bw_btn.setChecked(False)
        self.color_btn.setChecked(True)
        self.trigger_analysis()

    def change_copies(self, delta):
        new_copies = self._copies + delta
        if new_copies < 1: new_copies = 1
        if new_copies > 99: new_copies = 99
        if new_copies != self._copies:
            self._copies = new_copies
            self.copies_count_label.setText(str(self._copies))
            self.update_cost_display()

    def set_pdf_data(self, pdf_data, selected_pages):
        self.selected_pdf = pdf_data
        self.selected_pages = selected_pages
        self._copies = 1
        self.copies_count_label.setText(str(self._copies))
        self.set_bw_mode()
        self.trigger_analysis()

    def trigger_analysis(self):
        if not self.selected_pdf: return

        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            self.analysis_thread.wait()

        self.continue_btn.setEnabled(False) 
        self.analysis_results = None

        user_wants_color = (self._color_mode == "Color")

        if user_wants_color:
            self.cost_label.setText("Analyzing pages and calculating cost...")
            self.analysis_details_label.setText("This may take a moment for large documents...")
            
            pdf_path = self.selected_pdf['path']
            self.analysis_thread = AnalysisThread(self.analyzer, pdf_path, self.selected_pages, user_wants_color)
            self.analysis_thread.analysis_complete.connect(self.on_analysis_finished)
            self.analysis_thread.start()
        else:
            self.cost_label.setText("Calculating cost...")
            
            num_pages = len(self.selected_pages)
            base_cost = num_pages * self.analyzer.black_price
            
            bw_results = {
                'pricing': {
                    'base_cost': base_cost,
                    'black_pages_count': num_pages,
                    'color_pages_count': 0 
                },
                'page_analysis': {},
                'error': None
            }
            self.on_analysis_finished(bw_results)

    def on_analysis_finished(self, results):
        if results.get('error'):
            self.cost_label.setText("Error during analysis!")
            self.analysis_details_label.setText(results['error'])
            QMessageBox.critical(self, "Analysis Error", results['error'])
            return
        
        self.analysis_results = results
        self.continue_btn.setEnabled(True) 
        self.update_cost_display()

    def update_cost_display(self):
        if not self.analysis_results:
            return
        
        num_copies = self._copies
        base_cost = self.analysis_results['pricing']['base_cost']
        total_cost = base_cost * num_copies

        self.copies_count_label.setText(str(num_copies))
        self.cost_label.setText(f"Total Cost: ₱{total_cost:.2f}")

        b_count = self.analysis_results['pricing']['black_pages_count']
        c_count = self.analysis_results['pricing']['color_pages_count']
        if c_count > 0:
            details_text = f"Based on {num_copies} copies of ({b_count} B&W pages + {c_count} Color pages)"
        else:
            details_text = f"Based on {num_copies} copies of {b_count} Black & White pages"
        self.analysis_details_label.setText(details_text)
        
    def go_back(self):
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            self.analysis_thread.wait()
        self.main_app.show_screen('file_browser')

    def continue_to_payment(self):
        if not self.analysis_results:
            QMessageBox.warning(self, "Please Wait", "Cost calculation is still in progress.")
            return

        total_cost = self.analysis_results['pricing']['base_cost'] * self._copies
        payment_data = {
            'pdf_data': self.selected_pdf,
            'selected_pages': self.selected_pages,
            'copies': self._copies,
            'color_mode': self._color_mode,
            'total_cost': total_cost,
            'analysis': self.analysis_results
        }
        self.main_app.payment_screen.set_payment_data(payment_data)
        self.main_app.show_screen('payment')