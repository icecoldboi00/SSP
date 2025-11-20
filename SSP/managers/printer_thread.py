import os
import subprocess
import tempfile
import fitz  # PyMuPDF
from PyQt5.QtCore import QThread, pyqtSignal
from config import get_config
from managers.sms_manager import send_paper_jam_sms, send_printing_error_sms, send_no_paper_sms



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
        try:
            # Create temporary PDF with selected pages
            self.create_temp_pdf_with_selected_pages()
            if not self.temp_pdf_path:
                return

            # Build and execute CUPS print command
            command = self.build_print_command()
            config = get_config()
            # Note: copies are handled in PDF, so temp PDF will have (pages × copies) pages
            total_pages_in_pdf = len(self.selected_pages) * self.copies
            print(f"Printing: {len(self.selected_pages)} selected pages × {self.copies} copies = {total_pages_in_pdf} total pages, {self.color_mode}")
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
            # Clean up temp PDF if print failed
            # Main app will clean it up after ink analysis if success
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
            # For single-page documents with multiple copies: use CUPS -n flag (don't duplicate in PDF)
            # For multi-page documents: duplicate pages in PDF to avoid separator pages
            is_single_page = len(self.selected_pages) == 1
            
            if self.copies < 1:
                raise ValueError(f"Invalid copies value: {self.copies}. Must be at least 1.")
            
            if is_single_page and self.copies > 1:
                # Single page with multiple copies: just copy the page once, use CUPS -n flag
                print(f"Single page document with {self.copies} copies - using CUPS -n flag")
                for page_num in pages_0_indexed:
                    print(f"Copying page {page_num + 1} (0-indexed: {page_num})")
                    temp_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)
            else:
                # Multi-page or single copy: duplicate pages in PDF itself to avoid separator pages
                # Order: All pages of copy 1, then all pages of copy 2, etc.
                # Example: 2 copies of pages [1,2,3] = [page1, page2, page3, page1, page2, page3]
                pages_added = 0
                for copy_num in range(self.copies):
                    for page_num in pages_0_indexed:
                        print(f"Copy {copy_num + 1}/{self.copies}: Copying page {page_num + 1} (0-indexed: {page_num})")
                        temp_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)
                        pages_added += 1
                        
                        # Verify page was actually added
                        if len(temp_doc) != pages_added:
                            raise ValueError(f"Failed to add page {page_num + 1} - page count mismatch")
            
            # Verify page count before saving
            # For single-page with multiple copies, PDF should have 1 page (CUPS will handle copies)
            # For multi-page, PDF should have all pages duplicated
            if is_single_page and self.copies > 1:
                expected_pages = 1  # Single page, CUPS will duplicate
            else:
                expected_pages = len(self.selected_pages) * self.copies
            
            actual_pages = len(temp_doc)
            print(f"Temp PDF page count: {actual_pages} (expected: {expected_pages})")
            if actual_pages != expected_pages:
                error_msg = f"Page count mismatch! Expected {expected_pages}, got {actual_pages}"
                print(f"⚠ ERROR: {error_msg}")
                temp_doc.close()
                original_doc.close()
                raise ValueError(error_msg)
            
            # Save to temporary file
            fd, self.temp_pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="printjob-")
            os.close(fd)
            print(f"Saving temp PDF to: {self.temp_pdf_path}")
            temp_doc.save(self.temp_pdf_path, garbage=4, deflate=True)
            temp_doc.close()
            original_doc.close()
            
            # Verify temp file was created and check page count
            if os.path.exists(self.temp_pdf_path):
                file_size = os.path.getsize(self.temp_pdf_path)
                print(f"Temp PDF created successfully: {file_size} bytes")
                
                # Double-check page count by opening the saved file
                verify_doc = fitz.open(self.temp_pdf_path)
                verify_page_count = len(verify_doc)
                verify_doc.close()
                print(f"Verified temp PDF has {verify_page_count} pages")
                if verify_page_count != expected_pages:
                    error_msg = f"Saved PDF has wrong page count! Expected {expected_pages}, got {verify_page_count}"
                    print(f"⚠ ERROR: {error_msg}")
                    # Clean up the bad file
                    try:
                        os.remove(self.temp_pdf_path)
                    except:
                        pass
                    raise ValueError(error_msg)
                print(f"✓ Temp PDF verified: {verify_page_count} pages, {self.copies} copies of {len(self.selected_pages)} selected pages")
            else:
                raise Exception("Temp PDF file was not created")
            
        except Exception as e:
            print(f"Failed to create temporary PDF: {str(e)}")
            self.print_failed.emit(f"Failed to create temporary PDF: {str(e)}")
            self.temp_pdf_path = None

    def wait_for_print_completion(self, job_id):
        import time
        
        config = get_config()
        # Calculate timeout based on number of pages and copies
        # Base timeout: 1.5 minutes per page, minimum 3 minutes, maximum 30 minutes
        # This is a safety limit - job will complete as soon as printer is done
        estimated_pages = len(self.selected_pages) * self.copies
        base_timeout = max(180, estimated_pages * 90)  # At least 3 min, or 1.5 min per page
        max_wait_time = min(base_timeout, 1800)  # Cap at 30 minutes (safety limit)
        max_wait_time = max(max_wait_time, config.printer_timeout * 10)  # At least config timeout
        
        min_print_time = 15  # Minimum time to wait for physical printing (15 seconds)
        post_completion_wait = 5  # Wait 15 seconds after completion detection to ensure all pages printed
        check_interval = 3
        initial_startup_delay = 5  # Wait 5 seconds before first check to let printer start
        elapsed_time = 0
        completion_time = None
        media_empty_sms_sent = False
        
        print(f"Starting print completion monitoring (timeout: {max_wait_time}s, pages: {estimated_pages}, min_print_time: {min_print_time}s)")
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
                
                # Check CUPS job status directly as additional verification
                cups_job_still_active = self._check_cups_job_status(job_id)
                
                # Enhanced completion logic with minimum wait time
                if not printer_actively_printing and not cups_job_still_active:
                    # Ensure minimum print time has passed
                    if elapsed_time < min_print_time:
                        print(f"Waiting for minimum print time ({min_print_time}s) - {elapsed_time}s elapsed")
                        time.sleep(check_interval)
                        elapsed_time += check_interval
                        continue
                    
                    # No printer is actively printing and CUPS job is done, minimum time has passed
                    if completion_time is None:
                        completion_time = elapsed_time
                        print(f"Print job appears completed after {elapsed_time}s (printer idle, CUPS job done), monitoring for {post_completion_wait}s...")
                    else:
                        # Check if post-completion monitoring is complete
                        time_since_completion = elapsed_time - completion_time
                        if time_since_completion >= post_completion_wait:
                            print(f"Print job successful - no printers actively printing and CUPS job completed for {post_completion_wait}s")
                            return True
                else:
                    # Printer became active again or CUPS job still active - reset completion timer
                    if completion_time is not None:
                        if printer_actively_printing:
                            print(f"Printer became active again - resetting completion timer")
                        if cups_job_still_active:
                            print(f"CUPS job still active - resetting completion timer")
                        completion_time = None
                    if printer_actively_printing:
                        print(f"Waiting for printer '{target_printer}' to finish printing...")
                    if cups_job_still_active:
                        print(f"Waiting for CUPS job {job_id} to complete...")
                    
                time.sleep(check_interval)
                elapsed_time += check_interval
                    
            except Exception as e:
                print(f"Error checking print status: {e}")
                time.sleep(check_interval)
                elapsed_time += check_interval
        
        print(f"Print job timed out after {max_wait_time} seconds")
        # Final check: verify CUPS job status one more time
        if not self._check_cups_job_status(job_id):
            print(f"CUPS job {job_id} appears completed despite timeout - marking as success")
            return True
        return False
    
    def _check_cups_job_status(self, job_id):
        """Check if CUPS job is still in the queue"""
        try:
            # Check if job is still in CUPS queue
            result = subprocess.run(['lpstat', '-o'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                # Look for the job ID in the output
                for line in result.stdout.split('\n'):
                    if job_id in line:
                        # Job still in queue
                        return True
                # Job not found in queue - it's completed
                return False
            return False
        except Exception as e:
            print(f"Error checking CUPS job status: {e}")
            # On error, assume job might still be active to be safe
            return True

    def build_print_command(self):
        mode_str = "color" if self.color_mode == "Color" else "monochrome"
        
        command = [
            "lp",
            "-d", self.printer_name,
            "-o", f"print-color-mode={mode_str}",
        ]
        
        # Calculate total pages to print
        total_pages = len(self.selected_pages) * self.copies
        is_single_page_multiple_copies = len(self.selected_pages) == 1 and self.copies > 1
        
        # Try multiple ways to disable separator pages
        # Some printers use different option names or formats
        # Try both formats: "none" and "none,none" (for start and end)
        separator_disable_options = [
            "job-sheets=none,none",  # Disable both start and end separator pages
            "job-sheets=none",       # Alternative format
            "JobSheets=none,none",   # Capitalized version
            "job-billing=none",      # Disable billing pages
            "JobBilling=none",       # Capitalized billing
            "separator=none",        # Generic separator option
            "banner=none",           # Banner page option
        ]
        for opt in separator_disable_options:
            command.extend(["-o", opt])
        
        # For 10+ pages, add options to prevent job splitting or page breaks
        # Some printers add separator pages when jobs are split into batches
        if total_pages >= 10:
            print(f"Large job detected ({total_pages} pages) - adding options to prevent job splitting")
            # Options to prevent job splitting or page breaks
            anti_split_options = [
                "page-ranges=1-999999",  # Explicitly set page range to prevent splitting
                "number-up=1",           # Ensure single page per sheet
                "sides=one-sided",      # Force one-sided printing
            ]
            for opt in anti_split_options:
                command.extend(["-o", opt])
        
        # Handle copies:
        # - Single page with multiple copies: use CUPS -n flag (same as multi-page behavior)
        # - Multi-page documents: pages are already duplicated in PDF, so use -n 1
        if is_single_page_multiple_copies:
            # Use CUPS -n flag for single-page documents with multiple copies
            command.extend(["-n", str(self.copies)])
            print(f"Using CUPS -n {self.copies} for single-page document with multiple copies")
        else:
            # Multi-page: copies are handled in PDF itself, so always print 1 copy
            command.extend(["-n", "1"])
            print(f"Using CUPS -n 1 (copies handled in PDF)")
        
        # Add file path at the end
        command.append(self.temp_pdf_path)
        
        print(f"Print command: {' '.join(command)}")
        print(f"Copies value: {self.copies} (type: {type(self.copies)})")
        print(f"Separator page options included: {len(separator_disable_options)} options")
        
        # Verify PDF page count matches expected
        try:
            import fitz
            pdf_doc = fitz.open(self.temp_pdf_path)
            pdf_page_count = len(pdf_doc)
            expected_pages = len(self.selected_pages) * self.copies
            print(f"PDF verification: {pdf_page_count} pages in temp PDF (expected: {expected_pages})")
            if pdf_page_count != expected_pages:
                print(f"⚠ WARNING: PDF page count mismatch!")
            pdf_doc.close()
        except Exception as e:
            print(f"Could not verify PDF page count: {e}")
        
        return command

    def cleanup_temp_pdf(self):
        if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
            try:
                os.remove(self.temp_pdf_path)
            except OSError as e:
                print(f"Error cleaning up temp file: {e}")

