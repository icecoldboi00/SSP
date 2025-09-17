# screens/print_options/model.py

import fitz
import cv2
import numpy as np
from typing import List, Dict
from PyQt5.QtCore import QObject, pyqtSignal, QThread

class PDFColorAnalyzer:
    """Analyzes PDF pages to determine if they are black and white or colored."""
    
    def __init__(self, black_price: float, color_price: float):
        self.black_price = black_price
        self.color_price = color_price

    def is_page_black_only(self, page_image: np.ndarray,
                          color_tolerance: int = 15,
                          pixel_count_threshold: int = 200) -> bool:
        """Determines if a page image is black and white only."""
        if page_image.size == 0: 
            return True
        
        b, g, r = page_image[:, :, 0], page_image[:, :, 1], page_image[:, :, 2]
        channel_max = np.maximum(np.maximum(r, g), b)
        channel_min = np.minimum(np.minimum(r, g), b)
        color_diff = (channel_max - channel_min).astype(np.uint8)
        colored_pixel_count = np.count_nonzero(color_diff > color_tolerance)
        return colored_pixel_count < pixel_count_threshold

    def analyze_pdf_pages(self, pdf_path: str, pages_to_check: List[int], user_wants_color: bool, dpi: int = 150) -> Dict:
        """Analyzes PDF pages and calculates pricing."""
        results = {
            'page_analysis': {}, 
            'pricing': {'black_pages_count': 0, 'color_pages_count': 0, 'base_cost': 0},
            'error': None
        }
        
        try:
            pdf_document = fitz.open(pdf_path)
            for page_num_1_based in pages_to_check:
                page_num_0_based = page_num_1_based - 1
                if not (0 <= page_num_0_based < len(pdf_document)): 
                    continue

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
                results['page_analysis'][page_num_1_based] = {
                    'is_black_only': is_black_only, 
                    'final_price': page_price
                }

            pdf_document.close()
            return results
        except Exception as e:
            results['error'] = f"Error processing PDF: {str(e)}"
            return results

class AnalysisThread(QThread):
    """Thread for analyzing PDF pages in the background."""
    analysis_complete = pyqtSignal(dict)

    def __init__(self, analyzer, pdf_path, selected_pages, user_wants_color):
        super().__init__()
        self.analyzer = analyzer
        self.pdf_path = pdf_path
        self.selected_pages = selected_pages
        self.user_wants_color = user_wants_color
        self._is_running = True

    def run(self):
        if not self._is_running: 
            return
        results = self.analyzer.analyze_pdf_pages(self.pdf_path, self.selected_pages, self.user_wants_color)
        if self._is_running:
            self.analysis_complete.emit(results)
    
    def stop(self):
        self._is_running = False

class PrintOptionsModel(QObject):
    """Handles the data and business logic for the print options screen."""
    cost_updated = pyqtSignal(str, str)  # Emits cost text and details text
    analysis_started = pyqtSignal()
    analysis_completed = pyqtSignal(dict)  # Emits analysis results
    analysis_error = pyqtSignal(str)  # Emits error message
    show_message = pyqtSignal(str, str)  # Emits message title and text
    
    def __init__(self):
        super().__init__()
        self.analyzer = PDFColorAnalyzer(black_price=3.0, color_price=5.0)
        self.analysis_thread = None
        self.analysis_results = None
        
        self.selected_pdf = None
        self.selected_pages = None
        self._copies = 1
        self._color_mode = "Black and White"
    
    def set_pdf_data(self, pdf_data, selected_pages):
        """Sets the PDF data and selected pages."""
        self.selected_pdf = pdf_data
        self.selected_pages = selected_pages
        self._copies = 1
        self._color_mode = "Black and White"
        self.trigger_analysis()
    
    def set_color_mode(self, mode):
        """Sets the color mode (Black and White or Color)."""
        self._color_mode = mode
        self.trigger_analysis()
    
    def get_color_mode(self):
        """Returns the current color mode."""
        return self._color_mode
    
    def change_copies(self, delta):
        """Changes the number of copies by the given delta."""
        new_copies = self._copies + delta
        if new_copies < 1: 
            new_copies = 1
        if new_copies > 99: 
            new_copies = 99
        if new_copies != self._copies:
            self._copies = new_copies
            self.update_cost_display()
    
    def get_copies(self):
        """Returns the current number of copies."""
        return self._copies
    
    def trigger_analysis(self):
        """Triggers the PDF analysis based on current settings."""
        if not self.selected_pdf: 
            return

        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            self.analysis_thread.wait()

        self.analysis_results = None
        user_wants_color = (self._color_mode == "Color")

        if user_wants_color:
            self.analysis_started.emit()
            
            pdf_path = self.selected_pdf['path']
            self.analysis_thread = AnalysisThread(self.analyzer, pdf_path, self.selected_pages, user_wants_color)
            self.analysis_thread.analysis_complete.connect(self.on_analysis_finished)
            self.analysis_thread.start()
        else:
            # For black and white, calculate directly
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
        """Handles the completion of PDF analysis."""
        if results.get('error'):
            self.analysis_error.emit(results['error'])
            return
        
        self.analysis_results = results
        self.analysis_completed.emit(results)
        self.update_cost_display()
    
    def update_cost_display(self):
        """Updates the cost display based on current settings."""
        if not self.analysis_results:
            return
        
        num_copies = self._copies
        base_cost = self.analysis_results['pricing']['base_cost']
        total_cost = base_cost * num_copies

        cost_text = f"Total Cost: ₱{total_cost:.2f}"

        b_count = self.analysis_results['pricing']['black_pages_count']
        c_count = self.analysis_results['pricing']['color_pages_count']
        if c_count > 0:
            details_text = f"Based on {num_copies} copies of ({b_count} B&W pages + {c_count} Color pages)"
        else:
            details_text = f"Based on {num_copies} copies of {b_count} Black & White pages"
        
        self.cost_updated.emit(cost_text, details_text)
    
    def get_payment_data(self):
        """Returns the payment data for the current print job."""
        if not self.analysis_results:
            return None
        
        total_cost = self.analysis_results['pricing']['base_cost'] * self._copies
        return {
            'pdf_data': self.selected_pdf,
            'selected_pages': self.selected_pages,
            'copies': self._copies,
            'color_mode': self._color_mode,
            'total_cost': total_cost,
            'analysis': self.analysis_results
        }
    
    def stop_analysis(self):
        """Stops the current analysis thread."""
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            if not self.analysis_thread.wait(2000):
                print("Warning: Analysis thread did not stop gracefully")
                self.analysis_thread.terminate()
                self.analysis_thread.wait(1000)
