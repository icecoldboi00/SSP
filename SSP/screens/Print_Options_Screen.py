# screens/print_options_screen.py

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QComboBox, QFrame, QGridLayout, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

import fitz
import cv2
import numpy as np
from typing import List, Tuple, Dict

class PDFColorAnalyzer:
    # ## FIX: Set your fixed B&W price here
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
            'page_analysis': {}, 'pricing': {'black_pages_count': 0, 'color_pages_count': 0, 'base_cost': 0},
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
                price = self.black_price

                if not is_black_only and user_wants_color:
                    price = self.color_price
                    results['pricing']['color_pages_count'] += 1
                else:
                    results['pricing']['black_pages_count'] += 1

                results['pricing']['base_cost'] += price
                results['page_analysis'][page_num_1_based] = {'is_black_only': is_black_only, 'final_price': price}

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

        # ## FIX: Set your fixed prices here. The user requested 3 pesos for B&W.
        self.analyzer = PDFColorAnalyzer(black_price=3.0, color_price=8.0)
        self.analysis_thread = None
        self.analysis_results = None

        self.setup_ui()

    # ... setup_ui remains the same as the previous version ...
    def setup_ui(self):
        self.analysis_details_label = QLabel("Analysis details will appear here.")
        self.analysis_details_label.setStyleSheet("color: #aaa; font-size: 14px; margin-top: 5px;")
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("Printing Options")
        title.setStyleSheet("color: white; font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        layout.addWidget(title)
        options_frame = QFrame()
        options_frame.setStyleSheet("background-color: #2a2a4a; border-radius: 10px; padding: 20px;")
        options_layout = QGridLayout()
        color_label = QLabel("Color Mode:")
        color_label.setStyleSheet("color: white; font-size: 16px;")
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Black & White", "Color"])
        self.color_combo.setStyleSheet("QComboBox { ... }")
        copies_label = QLabel("Number of Copies:")
        copies_label.setStyleSheet("color: white; font-size: 16px;")
        self.copies_spin = QSpinBox()
        self.copies_spin.setMinimum(1)
        self.copies_spin.setMaximum(99)
        self.copies_spin.setStyleSheet("QSpinBox { ... }")
        options_layout.addWidget(color_label, 0, 0)
        options_layout.addWidget(self.color_combo, 0, 1)
        options_layout.addWidget(copies_label, 1, 0)
        options_layout.addWidget(self.copies_spin, 1, 1)
        options_frame.setLayout(options_layout)
        layout.addWidget(options_frame)
        self.cost_label = QLabel("Calculating cost...")
        self.cost_label.setStyleSheet("color: #33cc33; font-size: 20px; font-weight: bold; margin: 20px 0 0 0;")
        layout.addWidget(self.cost_label)
        layout.addWidget(self.analysis_details_label)
        buttons_layout = QHBoxLayout()
        back_btn = QPushButton("← Back to File Browser")
        back_btn.clicked.connect(self.go_back)
        back_btn.setStyleSheet("...")
        self.continue_btn = QPushButton("Continue to Payment →")
        self.continue_btn.clicked.connect(self.continue_to_payment)
        self.continue_btn.setStyleSheet("...")
        self.color_combo.currentTextChanged.connect(self.trigger_analysis)
        self.copies_spin.valueChanged.connect(self.update_cost_display)
        buttons_layout.addWidget(back_btn)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.continue_btn)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

    def set_pdf_data(self, pdf_data, selected_pages):
        self.selected_pdf = pdf_data
        self.selected_pages = selected_pages
        self.copies_spin.setValue(1)
        self.trigger_analysis()

    # ## FIX: This method now contains the core logic change.
    def trigger_analysis(self):
        """Decides whether to run the full analysis or do a simple B&W calculation."""
        if not self.selected_pdf: return

        # Stop any analysis that might be running from a previous selection.
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            self.analysis_thread.wait()

        self.continue_btn.setEnabled(False) # Always disable until calculation is done
        self.analysis_results = None

        user_wants_color = (self.color_combo.currentText() == "Color")

        if user_wants_color:
            # --- USER WANTS COLOR: Run the detailed background analysis ---
            self.cost_label.setText("Analyzing pages and calculating cost...")
            self.analysis_details_label.setText("This may take a moment for large documents...")
            
            pdf_path = self.selected_pdf['path']
            self.analysis_thread = AnalysisThread(self.analyzer, pdf_path, self.selected_pages, user_wants_color)
            self.analysis_thread.analysis_complete.connect(self.on_analysis_finished)
            self.analysis_thread.start()
        else:
            # --- USER WANTS B&W: Calculate cost directly, no thread needed ---
            self.cost_label.setText("Calculating cost...")
            
            num_pages = len(self.selected_pages)
            # Use the fixed B&W price from the analyzer instance
            base_cost = num_pages * self.analyzer.black_price
            
            # Create a "mock" result dictionary that looks like the real one
            # This allows us to reuse the on_analysis_finished logic
            bw_results = {
                'pricing': {
                    'base_cost': base_cost,
                    'black_pages_count': num_pages,
                    'color_pages_count': 0  # Explicitly zero
                },
                'page_analysis': {}, # No need for page-by-page data
                'error': None
            }
            # Immediately call the handler with our manually created result
            self.on_analysis_finished(bw_results)


    def on_analysis_finished(self, results):
        """This slot is called when the background thread is done OR for B&W direct calculation."""
        if results.get('error'):
            self.cost_label.setText("Error during analysis!")
            self.analysis_details_label.setText(results['error'])
            QMessageBox.critical(self, "Analysis Error", results['error'])
            return
        
        self.analysis_results = results
        self.continue_btn.setEnabled(True) # Re-enable the continue button
        self.update_cost_display()

    def update_cost_display(self):
        """Updates the cost labels using the stored analysis results. This is fast."""
        if not self.analysis_results:
            return
        
        num_copies = self.copies_spin.value()
        base_cost = self.analysis_results['pricing']['base_cost']
        total_cost = base_cost * num_copies

        self.cost_label.setText(f"Total Cost: ₱{total_cost:.2f}")

        # Update the details label for clarity
        b_count = self.analysis_results['pricing']['black_pages_count']
        c_count = self.analysis_results['pricing']['color_pages_count']
        if c_count > 0:
            details_text = f"Based on {num_copies} copies of ({b_count} B&W pages + {c_count} Color pages)"
        else:
            # Simpler message for pure B&W jobs
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

        total_cost = self.analysis_results['pricing']['base_cost'] * self.copies_spin.value()
        payment_data = {
            'pdf_data': self.selected_pdf,
            'selected_pages': self.selected_pages,
            'copies': self.copies_spin.value(),
            'color_mode': self.color_combo.currentText(),
            'total_cost': total_cost,
            'analysis': self.analysis_results
        }
        self.main_app.payment_screen.set_payment_data(payment_data)
        self.main_app.show_screen('payment')