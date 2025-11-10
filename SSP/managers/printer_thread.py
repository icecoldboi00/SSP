import os
import subprocess
import tempfile
from PyQt5.QtCore import QThread, pyqtSignal
from config import get_config
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

    def cleanup_temp_pdf(self):
        """Delete the temporary PDF file if it was created."""
        if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
            try:
                os.remove(self.temp_pdf_path)
            except OSError as e:
                print(f"Error cleaning up temp file: {e}")

