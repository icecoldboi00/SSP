import threading
import queue
from PyQt5.QtCore import QObject, pyqtSignal
from managers.ink_analysis_manager import InkAnalysisManager
from database.db_manager import DatabaseManager


class InkAnalysisOperation:
    def __init__(self, operation_type, data, callback=None):
        self.operation_type = operation_type
        self.data = data
        self.callback = callback
        self.result = None
        self.error = None


class InkAnalysisThreadManager(QObject):
    analysis_completed = pyqtSignal(dict)
    database_updated = pyqtSignal(bool)
    
    def __init__(self):
        """Initialize the ink analysis thread manager."""
        super().__init__()
        self.operation_queue = queue.Queue()
        self.db_manager = None
        self.ink_analysis_manager = None
        self.thread = None
        self.running = False
        
    def start(self):
        """Start the ink analysis worker thread."""
        if self.thread is None or not self.thread.is_alive():
            self.running = True
            self.thread = threading.Thread(target=self._ink_analysis_worker, daemon=True)
            self.thread.start()
    
    def stop(self):
        """Stop the ink analysis worker thread."""
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        
        # Close database connection if it exists
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close()
            print("Database connection closed in ink analysis thread manager")
    
    def _ink_analysis_worker(self):
        # Create managers in this thread
        self.db_manager = DatabaseManager()
        self.ink_analysis_manager = InkAnalysisManager(self.db_manager)
        
        while self.running:
            try:
                # Get operation from queue with timeout
                operation = self.operation_queue.get(timeout=0.1)
                
                operation.operation_type == "analyze_and_update"
                self._handle_analyze_and_update(operation)

                # Execute callback if provided
                if operation.callback:
                    operation.callback(operation)
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in ink analysis worker: {e}")
                
                # Log error to database
                try:
                    from utils.error_logger import log_error
                    log_error("Ink Analysis Worker Error", str(e), "ink_analysis_threader")
                except Exception as db_error:
                    print(f"Failed to log error to database: {db_error}")
                
                if operation and operation.callback:
                    operation.error = str(e)
                    operation.callback(operation)

    def analyze_and_update(self, pdf_path, selected_pages=None, copies=1, dpi=150, color_mode="Color", callback=None):
        operation = InkAnalysisOperation("analyze_and_update", {
            'pdf_path': pdf_path,
            'selected_pages': selected_pages,
            'copies': copies,
            'dpi': dpi,
            'color_mode': color_mode
        }, callback)
        self.operation_queue.put(operation)
        return operation


    def _handle_analyze_and_update(self, operation):
        try:
            pdf_path = operation.data['pdf_path']
            selected_pages = operation.data.get('selected_pages')
            copies = operation.data.get('copies', 1)
            dpi = operation.data.get('dpi', 150)
            color_mode = operation.data.get('color_mode', 'Color')
            
            # Perform analysis and update database
            result = self.ink_analysis_manager.analyze_and_update_after_print(
                pdf_path=pdf_path,
                selected_pages=selected_pages,
                copies=copies,
                dpi=dpi,
                color_mode=color_mode
            )
            
            operation.result = result
            self.analysis_completed.emit(result)
            
            # Emit database update status and updated CMYK levels
            if result.get('database_updated', False):
                self.database_updated.emit(True)
                
                # Get and emit updated CMYK levels
                updated_levels = self.db_manager.get_cmyk_ink_levels()
                if updated_levels:
                    self.analysis_completed.emit({
                        'success': True,
                        'database_updated': True,
                        'cmyk_levels': updated_levels
                    })
            else:
                self.database_updated.emit(False)
                
        except Exception as e:
            operation.error = str(e)
            print(f"Error in ink analysis: {e}")
            self.database_updated.emit(False)
    


