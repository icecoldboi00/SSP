from PyQt5.QtCore import QObject, pyqtSignal, QTimer
import subprocess

class ThankYouModel(QObject):
    status_updated = pyqtSignal(str, str)
    redirect_to_idle = pyqtSignal()
    admin_override_requested = pyqtSignal()
    admin_override_hidden = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # Redirect timer for auto-navigation back to idle
        self.redirect_timer = QTimer()
        self.redirect_timer.setSingleShot(True)
        self.redirect_timer.timeout.connect(self._on_timer_timeout)
        
        # Status check timer for fallback monitoring
        self.status_check_timer = QTimer()
        self.status_check_timer.timeout.connect(self._check_print_status)
        self.status_check_timer.setSingleShot(False)
        
        # Screen state tracking
        self.current_state = "initial"
        self.print_job_started = False
        self.print_job_finished = False
        self.error_type = None
        self._suppress_error = False
        
    def _on_timer_timeout(self):
        self.redirect_to_idle.emit()
        
    def on_enter(self, main_app):
        self.main_app = main_app
        
        # Prevent duplicate print job starts
        if self.print_job_started:
            print(f"Print job already started, skipping")
            return
        
        # Check if there's a valid print job to start
        if not hasattr(main_app, 'current_print_job') or not main_app.current_print_job:
            print(f"No valid print job available")
            return
        
        # Attempt to safely eject the USB drive before starting the print job.
        # At this point the selected PDF has already been copied to a temp session folder,
        # so the original USB is no longer needed for printing.
        try:
            if hasattr(main_app, 'usb_screen') and hasattr(main_app.usb_screen, 'model'):
                usb_manager = getattr(main_app.usb_screen.model, 'usb_manager', None)
                if usb_manager:
                    ok = usb_manager.eject_current_usb_drive()
                    if not ok:
                        print("USB eject reported failure (continuing to print)")
                else:
                    print("No USBFileManager instance available for eject")
            else:
                print("USB screen/model not available; skipping USB eject")
        except Exception as eject_error:
            print(f"Error while trying to eject USB drive: {eject_error}")
        
        # Set initial state
        self.current_state = "waiting"
        self.print_job_finished = False  # Reset finished flag for new print job
        self.status_updated.emit(
            "Your document is being processed.",
            "Please remove your USB drive."
        )
        self.redirect_timer.stop()
        
        # Hide admin override button when starting new print job
        self.admin_override_hidden.emit()
        
        # Connect to printer manager signals
        if hasattr(main_app, 'printer_manager'):
            try:
                main_app.printer_manager.print_job_successful.connect(self._on_print_success)
                # Also connect to failures - ensures error is shown even if user navigates away
                main_app.printer_manager.print_job_failed.connect(self._on_print_failed)
            except Exception as e:
                print(f"Error connecting printer signals: {e}")
            
            # Start print job
            self._start_print_job(main_app)
            
            # Start monitoring timers
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(0, self._start_timers)
        else:
            print("No printer manager found")
            self.redirect_timer.start(10000)
    
    def show_waiting_for_print(self):
        self.current_state = "waiting"
        # Hide admin override button during normal printing
        self.admin_override_hidden.emit()
        self.status_updated.emit(
            "Your document is being processed.",
            "Please remove your USB drive."
        )
    
    def show_printing_error(self, message: str):
        if self._suppress_error:
            return

        self._suppress_error = True
        QTimer.singleShot(400, lambda: setattr(self, '_suppress_error', False))

        self.current_state = "error"
        
        # Stop any existing safety timeout since we're now in error state
        if self.redirect_timer.isActive():
            self.redirect_timer.stop()
        
        # Check if this is a paper jam error
        is_paper_jam = "paper jam" in message.lower() or "jam" in message.lower()
        
        # Check if this is a low/no paper error
        is_low_paper = (
            "no paper" in message.lower() or 
            "media-empty" in message.lower() or 
            "media-needed" in message.lower() or
            "media empty" in message.lower() or
            "out of paper" in message.lower()
        )
        
        # Sanitize common verbose CUPS errors for better UX
        if "CUPS Error" in message:
            clean_message = "Could not communicate with the printer."
        elif is_paper_jam:
            clean_message = "Paper jam detected."
        elif is_low_paper:
            clean_message = "Low or no paper detected."
        else:
            clean_message = "An error occurred."
        
        self.error_type = "paper_jam" if is_paper_jam else ("low_paper" if is_low_paper else "printing_error")
        
        self.status_updated.emit(
            "ERROR OCCURRED",
            f"Error: {clean_message}\nPlease contact an administrator.\nFor incomplete transactions please contact phone number\n+63 976 291 2863"
        )
        
        # SMS notification is sent by main_app.on_print_failed() not here bro
        # Only log to database here
        try:
            from utils.error_logger import log_error
            # Log with appropriate error type
            if is_low_paper:
                log_error("Low Paper", message, "thank_you_screen")
            elif is_paper_jam:
                log_error("Paper Jam", message, "thank_you_screen")
            else:
                log_error("Printing Error", message, "thank_you_screen")
        except Exception as db_error:
            print(f"Failed to log error to database: {db_error}")
        
        self.admin_override_requested.emit()
    
    def show_no_paper_error(self, paper_count: int):
        self.current_state = "error"
        self.error_type = "no_paper"
        
        # Stop any existing safety timeout since we're now in error state
        if self.redirect_timer.isActive():
            self.redirect_timer.stop()
        
        if paper_count == 0:
            error_message = "No paper available. Paper count: 0"
            self.status_updated.emit(
                "NO PAPER AVAILABLE",
                "The printer is out of paper. Please contact an administrator.\nFor incomplete transactions please contact phone number\n+63 976 291 2863"
            )
        elif paper_count <= 3:
            error_message = f"Low paper detected. Paper count: {paper_count}"
            self.status_updated.emit(
                "LOW PAPER WARNING",
                f"Only {paper_count} page(s) remaining. Please contact an administrator.\nFor incomplete transactions please contact phone number\n+63 976 291 2863"
            )
        else:
            error_message = f"Low paper warning. Paper count: {paper_count}"
            self.status_updated.emit(
                "LOW PAPER WARNING",
                f"Only {paper_count} page(s) remaining. Please contact an administrator.\nFor incomplete transactions please contact phone number\n+63 976 291 2863"
            )
        
        # Log error to database
        try:
            from utils.error_logger import log_error
            log_error("Low Paper", error_message, "thank_you_screen")
        except Exception as db_error:
            print(f"Failed to log error to database: {db_error}")
        
        # Show admin override button
        self.admin_override_requested.emit()
    
    def show_paper_jam_error(self, message: str):
        self.current_state = "error"
        self.error_type = "paper_jam"
        
        # Stop any existing safety timeout since we're now in error state
        if self.redirect_timer.isActive():
            self.redirect_timer.stop()
        
        self.status_updated.emit(
            "PAPER JAM DETECTED",
            "Paper jam detected. Please contact an administrator.\nFor incomplete transactions please contact phone number\n+63 976 291 2863"
        )
        
        # Show admin override button
        self.admin_override_requested.emit()
    
    def handle_admin_override(self):
        self.current_state = "admin_override"
        self.status_updated.emit(
            "ADMIN OVERRIDE",
            "Navigating to admin screen"
        )
        # Hide admin override button since override is being processed
        self.admin_override_hidden.emit()
        # Navigate directly to admin screen
        if hasattr(self, 'main_app') and self.main_app:
            self.main_app.show_screen('admin')
    
    def _on_print_success(self):
        if self.redirect_timer.isActive():
            self.redirect_timer.stop()
        
        if self.status_check_timer.isActive():
            self.status_check_timer.stop()
        
        # Hide admin override button since print succeeded
        self.admin_override_hidden.emit()
        
        # Clean up temporary files after successful printing
        self._cleanup_temp_files()
        
        # Update state
        self.current_state = "completed"
        self.status_updated.emit(
            "Thank you for printing with us",
            "Kindly collect your documents."
        )

        # Start 5-second redirect timer
        self.redirect_timer.start(3000)
    
    def _cleanup_temp_files(self):
        try:
            print("Cleaning up temp files")
        
            from managers.usb_file_manager import USBFileManager
            
            # Create a temporary USB manager instance to access cleanup methods
            temp_usb_manager = USBFileManager()
            
            # Clean up all temp folders from previous sessions
            temp_usb_manager.cleanup_all_temp_folders()
            print("Cleaned up all temporary folders")
                
        except Exception as e:
            print(f"Error during temp file cleanup: {e}")
    
    def _start_print_job(self, main_app):
        if hasattr(main_app, 'current_print_job') and main_app.current_print_job:
            try:
                main_app.printer_manager.print_file(
                    file_path=main_app.current_print_job['file_path'],
                    selected_pages=main_app.current_print_job['selected_pages'],
                    copies=main_app.current_print_job['copies'],
                    color_mode=main_app.current_print_job['color_mode']
                )
                self.print_job_started = True
            except Exception as e:
                print(f"Error starting print job: {e}")
                self.show_printing_error(f"Failed to start print job: {e}")
        else:
            print(f"No print job details available")
            self.show_printing_error("No print job details available")
    
    def _check_print_status(self):
        # Only check if we're still waiting
        if self.current_state != "waiting":
            return
        
        try:
            result = subprocess.run(['lpstat', '-p'], capture_output=True, text=True, timeout=5)
            
            if result.returncode == 0:
                output = result.stdout
                output_lower = output.lower()
                
                # Get the actual printer name from printer manager instead of hardcoded value
                target_printer = None
                if hasattr(self, 'main_app') and hasattr(self.main_app, 'printer_manager'):
                    target_printer = self.main_app.printer_manager.printer_name
                
                if not target_printer:
                    target_printer = "HP_Smart_Tank_580_590_series_5E0E1D_USB"
                
                is_printing = False
                
                detailed_result = subprocess.run(['lpstat', '-l', '-p', target_printer], 
                                               capture_output=True, text=True, timeout=5)
                
                if detailed_result.returncode == 0:
                    # First, check header line for explicit printing/idle states
                    try:
                        header_line = detailed_result.stdout.split('\n', 1)[0].strip().lower()
                        if " now printing " in header_line or header_line.startswith(f"printer {target_printer.lower()} now printing"):
                            is_printing = True
                            print(f"'{target_printer}' printing")
                        elif " is idle." in header_line:
                            print(f"'{target_printer}' now idle")
                    except Exception:
                        pass

                    # Look for alerts line in the output
                    for line in detailed_result.stdout.split('\n'):
                        line = line.strip()
                        if line.startswith("Alerts:"):
                            alerts_text = line.replace("Alerts:", "").strip()
                            print(f"Printer alerts for {target_printer}: {alerts_text}")
                            
                            if alerts_text and alerts_text != "none":
                                alerts_found = [alert.strip() for alert in alerts_text.split()]
                                
                                # Check if printer is actively printing
                                if "cups-waiting-for-job-completed" in alerts_found:
                                    is_printing = True
                                    print(f"Printer '{target_printer}' still processing/printing (cups-waiting-for-job-completed)")
                                
                                # Check for specific error conditions
                                if "media-jam-error" in alerts_found or "paper-jam" in alerts_found:
                                    self.show_paper_jam_error(f"Paper jam detected on {target_printer}")
                                    return
                                elif "media-empty-error" in alerts_found or "media-needed-error" in alerts_found:
                                    self.show_printing_error(f"No paper detected on {target_printer}")
                                    return
                                elif "offline" in alerts_found or "stopped" in alerts_found:
                                    self.show_printing_error(f"Printer {target_printer} went offline")
                                    return
                                elif "error" in alerts_found:
                                    self.show_printing_error(f"Printer error on {target_printer}")
                                    return
                            else:
                                # No alerts found
                                print(f"{target_printer}: no alerts")
                            break
                
                # Do NOT mark complete here; rely on real printer signals.
                # Only manage safety timer while printing; avoid premature redirects.
                if not is_printing:
                    print(f"'{target_printer}' appears idle; waiting for official completion signal")
                else:
                    print(f"Still waiting for '{target_printer}' to finish printing")
                    
        except subprocess.TimeoutExpired:
            print("Fallback lpstat command timed out")
        except Exception as e:
            print(f"Fallback status check error: {e}")
    
    def _start_timers(self):
        # Start periodic printer status check as fallback (every 5 seconds)
        self.status_check_timer.start(5000)
        
        # Do not auto-redirect while printing; stay on Thank You until success/failure
    
    def _on_print_failed(self, error_message):
        self.show_printing_error(error_message)
    
    def on_leave(self):
        # Disconnect printer signals
        if hasattr(self, 'main_app') and hasattr(self.main_app, 'printer_manager'):
            try:
                self.main_app.printer_manager.print_job_successful.disconnect(self._on_print_success)
                self.main_app.printer_manager.print_job_failed.disconnect(self._on_print_failed)
            except:
                pass
        
        # Stop timers
        if self.redirect_timer.isActive():
            self.redirect_timer.stop()
        if self.status_check_timer.isActive():
            self.status_check_timer.stop()
        
        # Reset state for next transaction
        self.print_job_started = False
        self.print_job_finished = False
    
    def get_status_style(self, state):
        styles = {
            "printing": "color: #36454F; font-size: 56px; font-weight: bold;",
            "waiting": "color: #ffc107; font-size: 56px; font-weight: bold;",
            "completed": "color: #28a745; font-size: 56px; font-weight: bold;",
            "error": "color: #dc3545; font-size: 56px; font-weight: bold;"
        }
        return styles.get(state, styles["printing"])


# Low coin inventory alerts handled in InkAnalysisManager