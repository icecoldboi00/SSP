import fitz
import numpy as np
from typing import List, Dict
import os
from PyQt5.QtCore import QObject, pyqtSignal, QThread
from config import get_config

class PDFColorAnalyzer:
    def __init__(self, black_price: float = None, color_price: float = None):
        # Set pricing from .env file
        config = get_config()
        self.black_price = config.black_and_white_price
        self.color_price = config.color_price

    def is_page_black_only(self, page_image: np.ndarray, color_tolerance: int = None, pixel_count_threshold: int = None) -> bool:
        if page_image.size == 0: 
            return True
        
        config = get_config()
        color_tolerance = config.color_tolerance
        pixel_count_threshold = config.pixel_count_threshold
        
        # Compare all pixels on a page 
        b, g, r = page_image[:, :, 0], page_image[:, :, 1], page_image[:, :, 2] 
        # Get max value from RGB 
        channel_max = np.maximum(np.maximum(r, g), b)
        # Get min value from RGB 
        channel_min = np.minimum(np.minimum(r, g), b)
        # Max - Min and return as uint8
        color_diff = (channel_max - channel_min).astype(np.uint8)
        # Check if difference is within tolerance range for each pixel
        colored_pixel_count = np.count_nonzero(color_diff > color_tolerance)
        # Return 0 if colored and 1 if not 
        return colored_pixel_count < pixel_count_threshold

    def analyze_pdf_pages(self, pdf_path: str, pages_to_check: List[int], user_wants_color: bool, dpi: int = None) -> Dict:
        config = get_config()
        dpi = config.pdf_analysis_dpi
            
        results = {
            'page_analysis': {}, 
            'pricing': {'black_pages_count': 0, 'color_pages_count': 0, 'base_cost': 0},
            'error': None
        }
        
        pdf_document = fitz.open(pdf_path)
        for page_num_1_based in pages_to_check:
            page_num_0_based = page_num_1_based - 1
            if not (0 <= page_num_0_based < len(pdf_document)): 
                continue
            
            # Arrayed PDF pages
            page = pdf_document[page_num_0_based]
            mat = fitz.Matrix(dpi/72, dpi/72)
            # Make the page into 1D array [R, G, B, R, G,...]
            pix = page.get_pixmap(matrix=mat, alpha=False, colorspace=fitz.csRGB)
            # Convert the array into 3D array with position (x, y) and RGB values 0-255 (uint8)
            page_image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            # Pass converted page to function 
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
        if not self._is_running: 
            return
        results = self.analyzer.analyze_pdf_pages(self.pdf_path, self.selected_pages, self.user_wants_color)
        if self._is_running:
            self.analysis_complete.emit(results)
    
    def stop(self):
        self._is_running = False

class PrintOptionsModel(QObject):
    cost_updated = pyqtSignal(str, str)  # Emits cost text and details text
    analysis_started = pyqtSignal()
    analysis_completed = pyqtSignal(dict)  # Emits analysis results
    analysis_error = pyqtSignal(str)  # Emits error message
    show_message = pyqtSignal(str, str)  # Emits message title and text
    
    def __init__(self):
        super().__init__()
        config = get_config()
        self.analyzer = PDFColorAnalyzer() 
        self.analysis_thread = None
        self.analysis_results = None
        
        self.selected_pdf = None
        self.selected_pages = None
        self._copies = 1
        self._color_mode = config.default_color_mode
    
    def set_pdf_data(self, pdf_data, selected_pages):
        print(f"PDF data: {pdf_data}")
        print(f"Selected pages: {selected_pages}")
        self.selected_pdf = pdf_data
        self.selected_pages = selected_pages
        self._copies = 1
        config = get_config()
        self._color_mode = config.default_color_mode
        print(f"Checking for color...")
        self.trigger_analysis()
    
    def set_color_mode(self, mode):
        self._color_mode = mode
        self.trigger_analysis()
    
    def get_color_mode(self):
        return self._color_mode
    
    def change_copies(self, delta):
        config = get_config()
        new_copies = self._copies + delta
        if new_copies < config.min_copies: 
            new_copies = config.min_copies
        if new_copies > config.max_copies: 
            new_copies = config.max_copies
        if new_copies != self._copies:
            self._copies = new_copies
            self.update_cost_display()
    
    def get_copies(self):
        return self._copies
    
    def trigger_analysis(self):
        print(f"Selected_pdf: {self.selected_pdf}")
        print(f"Selected_pages: {self.selected_pages}")
        print(f"Color_mode: {self._color_mode}")
        
        if not self.selected_pdf: 
            print(f"No selected PDF, returning")
            return

        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            self.analysis_thread.wait()

        self.analysis_results = None
        user_wants_color = (self._color_mode == "Color")
        print(f"user_wants_color: {user_wants_color}")

        if user_wants_color:
            print(f"Starting color analysis thread")
            self.analysis_started.emit()
            
            pdf_path = self.selected_pdf['path']
            # Validate path before starting analysis
            if not pdf_path or not os.path.exists(pdf_path):
                error_msg = f"PDF file not found: {pdf_path}"
                print(error_msg)
                self.analysis_error.emit(error_msg)
                return
            self.analysis_thread = AnalysisThread(self.analyzer, pdf_path, self.selected_pages, user_wants_color)
            self.analysis_thread.analysis_complete.connect(self.on_analysis_finished)
            self.analysis_thread.start()
        else:
            # For black and white, calculate directly
            print(f"Calculating black and white cost directly")
            num_pages = len(self.selected_pages)
            base_cost = num_pages * self.analyzer.black_price
            print(f"num_pages: {num_pages}, base_cost: {base_cost}")
            
            bw_results = {
                'pricing': {
                    'base_cost': base_cost,
                    'black_pages_count': num_pages,
                    'color_pages_count': 0 
                },
                'page_analysis': {},
                'error': None
            }
            print(f"bw_results: {bw_results}")
            self.on_analysis_finished(bw_results)
    
    def on_analysis_finished(self, results):
        if results.get('error'):
            self.analysis_error.emit(results['error'])
            return
        
        self.analysis_results = results
        self.analysis_completed.emit(results)
        self.update_cost_display()
    
    def update_cost_display(self):
        if not self.analysis_results:
            print(f"No analysis results, returning")
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
        
        print(f"Emitting cost_updated signal: '{cost_text}' / '{details_text}'")
        self.cost_updated.emit(cost_text, details_text)
    
    def get_payment_data(self):
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
        if self.analysis_thread and self.analysis_thread.isRunning():
            self.analysis_thread.stop()
            if not self.analysis_thread.wait(2000):
                print("Warning: Analysis thread did not stop gracefully")
                self.analysis_thread.terminate()
                self.analysis_thread.wait(1000)
