import os
import subprocess
import tempfile
import threading
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QTimer
from config import get_config
from managers.ink_analysis_manager import InkAnalysisManager
from managers.sms_manager import send_paper_jam_sms, send_printing_error_sms, send_no_paper_sms

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
    print("PyMuPDF library found. PDF page selection is ENABLED.")
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("PyMuPDF library not found. PDF page selection will be DISABLED.")
    print("   Install with: pip install PyMuPDF")


class PrinterThread(QThread):
    print_success = pyqtSignal(str)  # Emits temp_pdf_path for ink analysis
    print_failed = pyqtSignal(str)
    print_waiting = pyqtSignal()

    def __init__(self, file_path, copies, color_mode, selected_pages, printer_name):
        super().__init__()
        self.file_path = file_path
        self.copies = copies
        self.color_mode = color_mode
        self.selected_pages = sorted(selected_pages)
        self.printer_name = printer_name
        self.temp_pdf_path = None

    def run(self):
        """Execute the complete print workflow."""
        if not PYMUPDF_AVAILABLE:
            self.print_failed.emit("PyMuPDF library is not installed. Please install with: pip install PyMuPDF")
            return

        try:
            # Create temporary PDF with selected pages
            self.create_temp_pdf_with_selected_pages()
            if not self.temp_pdf_path:
                return

            # Build and execute CUPS print command
            command = self.build_print_command()
            config = get_config()
            print(f"Printing: {len(self.selected_pages)} pages, {self.copies} copies, {self.color_mode}")
            print(f"Command: {' '.join(command)}")
            print(f"Temp PDF: {self.temp_pdf_path}")
            
            # Verify temp PDF exists before printing
            if not os.path.exists(self.temp_pdf_path):
                raise FileNotFoundError(f"Temporary PDF not found: {self.temp_pdf_path}")
            
            process = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=config.printer_timeout
            )
            
            print(f"CUPS output: {process.stdout}")
            if process.stderr:
                print(f"CUPS stderr: {process.stderr}")

            # Validate print job was accepted by CUPS
            if not process.stdout or "request id is" not in process.stdout:
                self.print_failed.emit("Print job was not accepted by CUPS. Check printer connection.")
                return
            
            # Extract job ID from CUPS response
            job_id = self._extract_job_id(process.stdout)
            if not job_id:
                return
            
            # Wait for print job to complete with active monitoring
            self.print_waiting.emit()
            completion_success = self.wait_for_print_completion(job_id)
            
            if not completion_success:
                return
            
            # Mark as succeeded so temp PDF isn't cleaned up in finally block
            self._print_succeeded = True
            
            # Emit success signal with temp PDF path for ink analysis
            # Main app will clean up temp PDF after ink analysis completes
            self.print_success.emit(self.temp_pdf_path)

        except subprocess.TimeoutExpired:
            self._handle_print_error("Printing command timed out.")
        except FileNotFoundError:
            self._handle_print_error("The 'lp' command was not found. Is CUPS installed?")
        except subprocess.CalledProcessError as e:
            self._handle_print_error(f"CUPS Error: {e.stderr.strip()}")
        except Exception as e:
            self._handle_print_error(f"An unexpected error occurred: {str(e)}")
        finally:
            # Only clean up temp PDF if print failed
            # On success, main app will clean it up after ink analysis
            if not hasattr(self, '_print_succeeded'):
                self.cleanup_temp_pdf()

    def _extract_job_id(self, cups_output):
        try:
            parts = cups_output.split("request id is")
            if len(parts) > 1:
                job_id_part = parts[1].strip()
                job_id = job_id_part.split()[0].split('(')[0]
                print(f"Print job ID: {job_id}")
                return job_id
            else:
                self.print_failed.emit("Could not extract print job ID from CUPS response.")
                return None
        except Exception as e:
            print(f"Error extracting job ID: {e}")
            self.print_failed.emit(f"Error processing CUPS response: {e}")
            return None

    def _handle_print_error(self, error_message):
        print(f"ERROR: {error_message}")
        
        # Send SMS notification
        try:
            send_printing_error_sms(error_message)
        except Exception as sms_error:
            print(f"Failed to send SMS notification: {sms_error}")
        
        # Log error to database
        try:
            from utils.error_logger import log_error
            log_error("Printing Error", error_message, "printer_manager")
        except Exception as db_error:
            print(f"Failed to log error to database: {db_error}")
        
        self.print_failed.emit(error_message)

    def create_temp_pdf_with_selected_pages(self):
        try:
            print(f"Creating temp PDF with pages: {self.selected_pages}")
            print(f"Source file: {self.file_path}")
            
            # Verify source file exists
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"Source PDF file not found: {self.file_path}")
            
            original_doc = fitz.open(self.file_path)
            print(f"Original PDF has {len(original_doc)} pages")
            
            # Validate page numbers
            max_page = len(original_doc)
            invalid_pages = [p for p in self.selected_pages if p < 1 or p > max_page]
            if invalid_pages:
                raise ValueError(f"Invalid page numbers: {invalid_pages}. PDF has {max_page} pages.")
            
            pages_0_indexed = [p - 1 for p in self.selected_pages]
            print(f"Converting to 0-indexed pages: {pages_0_indexed}")
            
            temp_doc = fitz.open()
            
            # Copy selected pages
            for page_num in pages_0_indexed:
                print(f"Copying page {page_num + 1} (0-indexed: {page_num})")
                temp_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)
            
            # Save to temporary file
            fd, self.temp_pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="printjob-")
            os.close(fd)
            print(f"Saving temp PDF to: {self.temp_pdf_path}")
            temp_doc.save(self.temp_pdf_path, garbage=4, deflate=True)
            temp_doc.close()
            original_doc.close()
            
            # Verify temp file was created
            if os.path.exists(self.temp_pdf_path):
                file_size = os.path.getsize(self.temp_pdf_path)
                print(f"Temp PDF created successfully: {file_size} bytes")
            else:
                raise Exception("Temp PDF file was not created")
            
        except Exception as e:
            print(f"Failed to create temporary PDF: {str(e)}")
            self.print_failed.emit(f"Failed to create temporary PDF: {str(e)}")
            self.temp_pdf_path = None

    def wait_for_print_completion(self, job_id):
        import time
        
        config = get_config()
        max_wait_time = config.printer_timeout * 10
        min_print_time = 15  # Minimum time to wait for physical printing (15 seconds)
        post_completion_wait = 15  # Wait 15 seconds after completion detection to ensure all pages printed
        check_interval = 3
        initial_startup_delay = 5  # Wait 5 seconds before first check to let printer start
        elapsed_time = 0
        completion_time = None
        media_empty_sms_sent = False
        
        print(f"Starting print completion monitoring (timeout: {max_wait_time}s, min_print_time: {min_print_time}s)")
        print(f"Waiting {initial_startup_delay}s for printer to start processing job...")
        time.sleep(initial_startup_delay)
        elapsed_time += initial_startup_delay
        
        while elapsed_time < max_wait_time:
            try:
                # Check printer status using alerts-based detection
                # Use the configured printer name instead of a hardcoded value
                target_printer = self.printer_name
                printer_actively_printing = False
                
                # Get printer alerts to determine status
                alerts_result = subprocess.run(['lpstat', '-l', '-p', target_printer], 
                                             capture_output=True, text=True)
                if alerts_result.returncode == 0:
                    # If lpstat reports "now printing", consider it actively printing
                    try:
                        lpstat_out_lower = alerts_result.stdout.lower()
                        if " now printing " in lpstat_out_lower or lpstat_out_lower.startswith(f"printer {target_printer.lower()} now printing"):
                            printer_actively_printing = True
                            printer_was_active = True
                            print(f"Printer '{target_printer}' is actively printing (lpstat now printing)")
                    except Exception:
                        pass
                    # Look for alerts line in the output
                    for line in alerts_result.stdout.split('\n'):
                        line = line.strip()
                        if line.startswith("Alerts:"):
                            alerts_text = line.replace("Alerts:", "").strip()
                            print(f"Printer alerts for {target_printer}: {alerts_text}")
                            
                            if alerts_text and alerts_text != "none":
                                alerts_found = [alert.strip() for alert in alerts_text.split()]
                                
                                # Check if printer is actively printing (has cups-waiting-for-job-completed)
                                if "cups-waiting-for-job-completed" in alerts_found:
                                    printer_actively_printing = True
                                    printer_was_active = True
                                    print(f"Printer '{target_printer}' still processing/printing (cups-waiting-for-job-completed)")
                                
                                # Check for specific error conditions
                                if "media-jam-error" in alerts_found or "paper-jam" in alerts_found:
                                    print(f"Paper jam detected on {target_printer}")
                                    try:
                                        send_paper_jam_sms()
                                    except Exception as e:
                                        print(f"Failed to send SMS: {e}")
                                    self.print_failed.emit(f"Paper jam detected on {target_printer}")
                                    return False
                                elif "media-empty-error" in alerts_found or "media-needed-error" in alerts_found:
                                    print(f"No paper detected on {target_printer}")
                                    try:
                                        send_no_paper_sms()
                                    except Exception as e:
                                        print(f"Failed to send SMS: {e}")
                                    self.print_failed.emit(f"No paper detected on {target_printer}")
                                    return False
                                elif "media-empty-report" in alerts_found:
                                    # Treat as hard no-paper error to surface on UI
                                    print(f"Paper tray empty report on {target_printer}")
                                    if not media_empty_sms_sent:
                                        try:
                                            send_no_paper_sms()
                                            media_empty_sms_sent = True
                                            print("No paper SMS sent (report)")
                                        except Exception as e:
                                            print(f"Failed to send SMS: {e}")
                                    self.print_failed.emit(f"No paper detected on {target_printer}")
                                    return False
                                elif "offline" in alerts_found or "stopped" in alerts_found:
                                    print(f"Printer offline: {target_printer}")
                                    self.print_failed.emit(f"Printer {target_printer} is offline")
                                    return False
                                elif "error" in alerts_found:
                                    print(f"Printer error detected on {target_printer}")
                                    self.print_failed.emit(f"Printer error on {target_printer}")
                                    return False
                            else:
                                # No alerts found
                                print(f"Printer '{target_printer}': no alerts")
                            break
                
                # Enhanced completion logic with minimum wait time
                if not printer_actively_printing:
                    # Ensure minimum print time has passed
                    if elapsed_time < min_print_time:
                        print(f"Waiting for minimum print time ({min_print_time}s) - {elapsed_time}s elapsed")
                        time.sleep(check_interval)
                        elapsed_time += check_interval
                        continue
                    
                    # No printer is actively printing and minimum time has passed
                    if completion_time is None:
                        completion_time = elapsed_time
                        print(f"Print job appears completed after {elapsed_time}s, monitoring for {post_completion_wait}s...")
                    else:
                        # Check if post-completion monitoring is complete
                        time_since_completion = elapsed_time - completion_time
                        if time_since_completion >= post_completion_wait:
                            print(f"Print job successful - no printers actively printing for {post_completion_wait}s")
                            return True
                else:
                    # Printer became active again - reset completion timer
                    if completion_time is not None:
                        print(f"Printer became active again - resetting completion timer")
                        completion_time = None
                    print(f"Waiting for printer '{target_printer}' to finish printing...")
                    
                time.sleep(check_interval)
                elapsed_time += check_interval
                    
            except Exception as e:
                print(f"Error checking print status: {e}")
                time.sleep(check_interval)
                elapsed_time += check_interval
        
        print(f"Print job timed out after {max_wait_time} seconds")
        return False

    def build_print_command(self):
        mode_str = "color" if self.color_mode == "Color" else "monochrome"
        
        command = [
            "lp",
            "-d", self.printer_name,
            "-o", f"print-color-mode={mode_str}",
            self.temp_pdf_path
        ]
        
        # Add copies if more than 1
        if self.copies > 1:
            command.insert(-1, "-n")
            command.insert(-1, str(self.copies))
        
        return command


    def _check_printer_status(self):
        try:
            # First check the specific configured printer
            result = subprocess.run(['lpstat', '-p', self.printer_name], 
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                # If specific printer not found, check all printers for errors
                print(f"Configured printer '{self.printer_name}' not found, checking all printers")
                return self._check_all_printers_status()
            
            output = result.stdout.lower()
            
            # Check for various error conditions
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
    
    def _check_all_printers_status(self):
        try:
            result = subprocess.run(['lpstat', '-p'], capture_output=True, text=True)
            
            if result.returncode != 0:
                return {
                    'status': 'error',
                    'message': 'Failed to get printer status',
                    'details': result.stderr.strip()
                }
            
            output = result.stdout.lower()
            
            # Check for errors across all printers
            if 'jam' in output or 'paper jam' in output:
                return {
                    'status': 'paper_jam',
                    'message': 'Paper jam detected on one or more printers',
                    'details': 'Please clear the paper jam and try again'
                }
            elif 'offline' in output or 'stopped' in output:
                return {
                    'status': 'offline',
                    'message': 'One or more printers are offline or stopped',
                    'details': 'Please check printer connections and power'
                }
            elif 'error' in output:
                return {
                    'status': 'error',
                    'message': 'Printer error detected',
                    'details': output
                }
            else:
                return {
                    'status': 'ready',
                    'message': 'Printers are ready',
                    'details': 'Printers are available for printing'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Error checking all printers status: {e}",
                'details': str(e)
            }

    def cleanup_temp_pdf(self):
        """Delete the temporary PDF file if it was created."""
        if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
            try:
                os.remove(self.temp_pdf_path)
            except OSError as e:
                print(f"Error cleaning up temp file: {e}")


class PrinterManager(QObject):
    print_job_successful = pyqtSignal()
    print_job_failed = pyqtSignal(str)
    print_job_waiting = pyqtSignal()

    def __init__(self):
        """Initialize printer manager."""
        super().__init__()
        config = get_config()
        self.printer_name = config.printer_name
        self.print_thread = None
        self.check_printer_availability()

    def print_file(self, file_path, copies, color_mode, selected_pages):
        print(f"📄 Print request: {len(selected_pages)} pages × {copies} copies ({color_mode})")
        
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
            print(f"Checking printer availability for: {self.printer_name}")
            
            # Check if lp command exists
            result = subprocess.run(['which', 'lp'], capture_output=True, text=True)
            if result.returncode != 0:
                print("'lp' command not found. Is CUPS installed?")
                print("   Install CUPS: sudo apt-get install cups")
                return False
            print("CUPS lp command found")
            
            # Check if CUPS daemon is running
            try:
                result = subprocess.run(['pgrep', 'cupsd'], capture_output=True, text=True)
                if result.returncode != 0:
                    print("CUPS daemon (cupsd) is not running")
                    print("   Start CUPS: sudo systemctl start cups")
                    return False
                print("CUPS daemon is running")
            except Exception as e:
                print(f"Error checking CUPS daemon: {e}")
                return False
                
            # List all available printers first
            try:
                result = subprocess.run(['lpstat', '-p'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    print(f"Available printers:")
                    for line in result.stdout.split('\n'):
                        if line.strip():
                            print(f"   {line}")
                else:
                    print("Could not list printers")
            except Exception as e:
                print(f"Error listing printers: {e}")
                
            # Check if printer exists
            result = subprocess.run(['lpstat', '-p', self.printer_name], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                print(f"Printer '{self.printer_name}' not found")
                print(f"   Available printers listed above")
                print(f"   Update printer name in config.py")
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
        """Handle print thread completion."""
        self.print_thread = None
