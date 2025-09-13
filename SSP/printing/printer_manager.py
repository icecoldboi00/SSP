# printing/printer_manager.py
import os
import subprocess
import tempfile
from PyQt5.QtCore import QObject, QThread, pyqtSignal

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# IMPORTANT: Replace this with your exact printer name found via `lpstat -p`
PRINTER_NAME = "HP_Smart_Tank_580_590_series_5E0E1D_USB"

class PrinterThread(QThread):
    """
    Handles the actual printing task in a background thread to avoid freezing the GUI.
    """
    print_success = pyqtSignal()
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
        """The main logic for the printing thread."""
        if not PYMUPDF_AVAILABLE:
            self.print_failed.emit("PyMuPDF library is not installed.")
            return

        try:
            # Step 1: Create a temporary PDF with only the selected pages
            self.create_temp_pdf_with_selected_pages()
            if not self.temp_pdf_path:
                return # Error already emitted inside the creation method

            # Step 2: Construct the CUPS lp command
            command = self.build_print_command()
            mode_str = "color" if self.color_mode == "Color" else "monochrome"
            print(f"Executing print command: {' '.join(command)}")
            print(f"Printing file: {self.temp_pdf_path}")
            print(f"Printer: HP_Smart_Tank_580_590_series_5E0E1D_USB")
            print(f"Color mode: {self.color_mode} -> {mode_str}")
            print(f"Copies: {self.copies}")

            # Step 3: Execute the command and wait for it to complete
            process = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                check=True,  # Raises CalledProcessError on non-zero exit codes
                timeout=180  # 3 minute timeout
            )

            # Step 4: Check the result and wait for print job completion
            print(f"Print job sent to CUPS successfully. stdout: {process.stdout}")
            
            # Extract job ID from the output (format: "request id is HP_Smart_Tank_580_590_series_5E0E1D_USB-1 (1 file(s))")
            job_id = None
            if "request id is" in process.stdout:
                try:
                    job_id = process.stdout.split("request id is")[1].split()[0]
                    print(f"Print job ID: {job_id}")
                except:
                    print("Could not extract job ID from output")
            
            # Wait for the print job to actually complete
            if job_id:
                # Signal that we're now waiting for actual printing to complete
                self.print_waiting.emit()
                self.wait_for_print_completion(job_id)
            else:
                # If we can't get job ID, wait a reasonable time for printing
                print("Waiting 30 seconds for print job to complete...")
                self.print_waiting.emit()
                import time
                time.sleep(30)
            
            self.print_success.emit()

        except subprocess.TimeoutExpired:
            self.print_failed.emit("Printing command timed out.")
        except FileNotFoundError:
            self.print_failed.emit("The 'lp' command was not found. Is CUPS installed?")
        except subprocess.CalledProcessError as e:
            error_message = f"CUPS Error: {e.stderr.strip()}"
            print(error_message)
            self.print_failed.emit(error_message)
        except Exception as e:
            self.print_failed.emit(f"An unexpected error occurred: {str(e)}")
        finally:
            # Step 5: Clean up the temporary file
            self.cleanup_temp_pdf()

    def create_temp_pdf_with_selected_pages(self):
        """
        Creates a new PDF file containing only the pages the user selected.
        """
        try:
            original_doc = fitz.open(self.file_path)
            # fitz requires a 0-indexed list of pages
            pages_0_indexed = [p - 1 for p in self.selected_pages]
            
            temp_doc = fitz.open()  # Create a new empty PDF
            
            # Copy each selected page individually (compatible with older PyMuPDF versions)
            for page_num in pages_0_indexed:
                temp_doc.insert_pdf(original_doc, from_page=page_num, to_page=page_num)
            
            # Save to a temporary file
            fd, self.temp_pdf_path = tempfile.mkstemp(suffix=".pdf", prefix="printjob-")
            os.close(fd)
            temp_doc.save(self.temp_pdf_path, garbage=4, deflate=True)
            temp_doc.close()
            original_doc.close()
            print(f"Created temporary PDF for printing at: {self.temp_pdf_path}")
        except Exception as e:
            error_msg = f"Failed to create temporary PDF: {str(e)}"
            print(error_msg)
            self.print_failed.emit(error_msg)
            self.temp_pdf_path = None

    def wait_for_print_completion(self, job_id):
        """Wait for the print job to actually complete."""
        import time
        
        print(f"Waiting for print job {job_id} to complete...")
        max_wait_time = 300  # 5 minutes maximum wait
        check_interval = 5   # Check every 5 seconds
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            try:
                # Check if the job is still in the queue
                result = subprocess.run(['lpstat', '-o', job_id], 
                                      capture_output=True, text=True)
                
                if result.returncode != 0 or not result.stdout.strip():
                    # Job is no longer in the queue, it's completed
                    print(f"Print job {job_id} completed after {elapsed_time} seconds")
                    return True
                else:
                    print(f"Print job {job_id} still printing... ({elapsed_time}s elapsed)")
                    time.sleep(check_interval)
                    elapsed_time += check_interval
                    
            except Exception as e:
                print(f"Error checking print job status: {e}")
                time.sleep(check_interval)
                elapsed_time += check_interval
        
        print(f"Print job {job_id} timed out after {max_wait_time} seconds")
        return False

    def build_print_command(self):
        """Constructs the list of arguments for the subprocess call."""
        mode_str = "color" if self.color_mode == "Color" else "monochrome"
        
        # Use the exact command format specified for Raspberry Pi
        command = [
            "lp",
            "-d", "HP_Smart_Tank_580_590_series_5E0E1D_USB",
            "-o", f"print-color-mode={mode_str}",
            self.temp_pdf_path
        ]
        
        # Add copies if more than 1
        if self.copies > 1:
            command.insert(-1, "-n")
            command.insert(-1, str(self.copies))
        
        return command

    def cleanup_temp_pdf(self):
        """Deletes the temporary PDF file if it was created."""
        if self.temp_pdf_path and os.path.exists(self.temp_pdf_path):
            try:
                os.remove(self.temp_pdf_path)
                print(f"Cleaned up temporary file: {self.temp_pdf_path}")
            except OSError as e:
                print(f"Error cleaning up temp file {self.temp_pdf_path}: {e}")

class PrinterManager(QObject):
    """
    Manages print jobs by spawning PrinterThread instances.
    """
    print_job_successful = pyqtSignal()
    print_job_failed = pyqtSignal(str)
    print_job_waiting = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.printer_name = PRINTER_NAME
        self.print_thread = None
        self.check_printer_availability()

    def print_file(self, file_path, copies, color_mode, selected_pages):
        """
        Initiates a new print job in a background thread.
        """
        print(f"Received print request for {file_path}")
        print(f"Printer name: {self.printer_name}")
        print(f"Copies: {copies}, Color mode: {color_mode}, Pages: {selected_pages}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            self.print_job_failed.emit(f"File not found: {file_path}")
            return
            
        self.print_thread = PrinterThread(
            file_path=file_path,
            copies=copies,
            color_mode=color_mode,
            selected_pages=selected_pages,
            printer_name=self.printer_name
        )
        self.print_thread.print_success.connect(self.print_job_successful.emit)
        self.print_thread.print_failed.connect(self.print_job_failed.emit)
        self.print_thread.print_waiting.connect(self.print_job_waiting.emit)
        self.print_thread.finished.connect(self.on_thread_finished)
        self.print_thread.start()

    def check_printer_availability(self):
        """Check if the configured printer is available."""
        try:
            # Check if lp command is available
            result = subprocess.run(['which', 'lp'], capture_output=True, text=True)
            if result.returncode != 0:
                print("WARNING: 'lp' command not found. CUPS may not be installed.")
                return False
                
            # Check if printer exists
            result = subprocess.run(['lpstat', '-p', self.printer_name], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                print(f"WARNING: Printer '{self.printer_name}' not found.")
                print("Available printers:")
                subprocess.run(['lpstat', '-p'], capture_output=False)
                return False
                
            print(f"Printer '{self.printer_name}' is available.")
            return True
            
        except Exception as e:
            print(f"Error checking printer availability: {e}")
            return False

    def on_thread_finished(self):
        print("Print thread has finished.")
        self.print_thread = None