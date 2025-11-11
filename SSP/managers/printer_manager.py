import os
import subprocess
from PyQt5.QtCore import QObject, pyqtSignal
from config import get_config
from managers.printer_thread import PrinterThread


class PrinterManager(QObject):
    print_job_successful = pyqtSignal()
    print_job_failed = pyqtSignal(str)
    print_job_waiting = pyqtSignal()

    def __init__(self):
        super().__init__()
        config = get_config()
        self.printer_name = config.printer_name
        self.print_thread = None
        self.check_printer_availability()

    def print_file(self, file_path, copies, color_mode, selected_pages): 
        # Prevent duplicate print jobs
        if hasattr(self, 'print_thread') and self.print_thread and self.print_thread.isRunning():
            print("Print job already running, ignoring duplicate request")
            return
        
        # Verify printer is available
        if not self.check_printer_availability():
            self.print_job_failed.emit("Printer is not available. Please check printer connection.")
            return
        
        # Verify file exists
        if not os.path.exists(file_path):
            self.print_job_failed.emit(f"File not found: {file_path}")
            return
            
        # Create and start print thread
        self.print_thread = PrinterThread(
            file_path=file_path,
            copies=copies,
            color_mode=color_mode,
            selected_pages=selected_pages,
            printer_name=self.printer_name
        )
        self.print_thread.print_success.connect(self._on_print_success)
        self.print_thread.print_failed.connect(self.print_job_failed.emit)
        self.print_thread.print_waiting.connect(self.print_job_waiting.emit)
        self.print_thread.finished.connect(self.on_thread_finished)
        self.print_thread.start()

    def check_printer_availability(self):
        try:      
            # Check if CUPS daemon is running
            try:
                result = subprocess.run(['pgrep', 'cupsd'], capture_output=True, text=True)
                if result.returncode != 0:
                    return False
                print("CUPS daemon is running")
            except Exception as e:
                print(f"Error checking CUPS daemon: {e}")
                return False
                
            # Check if printer exists
            result = subprocess.run(['lpstat', '-p', self.printer_name], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print(f"Printer '{self.printer_name}' not found")
                return False
            print(f"Printer '{self.printer_name}' found")
            
            # Check printer state
            output = result.stdout.lower()
            print(f"Printer status: {result.stdout.strip()}")
            
            if 'offline' in output or 'stopped' in output:
                print(f"Printer is offline or stopped")
                return False
            elif 'jam' in output:
                print(f"Paper jam detected")
                return False
            elif 'error' in output:
                print(f"Printer error detected")
                return False
            else:
                print(f"Printer is ready")
            return True
            
        except Exception as e:
            print(f"Error checking printer availability: {e}")
            return False

    def check_printer_status(self):
        try:
            result = subprocess.run(['lpstat', '-p', self.printer_name], 
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                return {
                    'status': 'error',
                    'message': f"Printer '{self.printer_name}' not found or not responding",
                    'details': result.stderr.strip()
                }
            
            output = result.stdout.lower()
            
            if 'jam' in output or 'paper jam' in output:
                return {
                    'status': 'paper_jam',
                    'message': 'Paper jam detected',
                    'details': 'Please clear the paper jam and try again'
                }
            elif 'offline' in output or 'stopped' in output:
                return {
                    'status': 'offline',
                    'message': 'Printer is offline or stopped',
                    'details': 'Please check printer connection and power'
                }
            elif 'error' in output:
                return {
                    'status': 'error',
                    'message': 'Printer error detected',
                    'details': output
                }
            elif 'idle' in output or 'ready' in output:
                return {
                    'status': 'ready',
                    'message': 'Printer is ready',
                    'details': 'Printer is available for printing'
                }
            else:
                return {
                    'status': 'unknown',
                    'message': 'Unknown printer status',
                    'details': output
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Error checking printer status: {e}",
                'details': str(e)
            }

    def check_for_paper_jam(self):
        status = self.check_printer_status()
        return status['status'] == 'paper_jam'

    def _on_print_success(self, temp_pdf_path):
        # Store temp PDF path so main app can clean it up after ink analysis
        self.last_temp_pdf_path = temp_pdf_path
        self.print_job_successful.emit()
    
    def cleanup_last_temp_pdf(self):
        if hasattr(self, 'last_temp_pdf_path') and self.last_temp_pdf_path:
            try:
                import os
                if os.path.exists(self.last_temp_pdf_path):
                    os.remove(self.last_temp_pdf_path)
                    print(f"Cleaned up temp PDF: {self.last_temp_pdf_path}")
                self.last_temp_pdf_path = None
            except Exception as e:
                print(f"Error cleaning up temp PDF: {e}")
    
    def on_thread_finished(self):
        self.print_thread = None
