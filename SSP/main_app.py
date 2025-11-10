import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt5.QtCore import Qt, QTimer
from screens.idle import IdleController
from screens.usb import USBController
from screens.file_browser import FileBrowserController
from screens.payment import PaymentController
from screens.print_options import PrintOptionsController
from screens.admin import AdminController
from screens.data_viewer import DataViewerController
from screens.thank_you import ThankYouController
from database.models import init_db
from managers.usb_file_manager import USBFileManager
from managers.printer_manager import PrinterManager
from managers.db_threader import DatabaseThreadManager
from managers.ink_analysis_threader import InkAnalysisThreadManager
from managers.sms_manager import cleanup_sms


class PrintingSystemApp(QMainWindow):
    # Screen index mapping for stacked widget navigation
    SCREEN_MAP = {
        'idle': 0,
        'usb': 1,
        'file_browser': 2,
        'printing_options': 3,
        'payment': 4,
        'admin': 5,
        'data_viewer': 6,
        'thank_you': 7
    }
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Printing System GUI")
        
        # Get screen dimensions and set appropriate window size
        self._setup_display()

        # Initialize stacked widget for screen management
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.db_threader = DatabaseThreadManager()
        self.ink_analysis_threader = InkAnalysisThreadManager()
        
        self.idle_screen = IdleController(self)
        self.usb_screen = USBController(self)
        self.file_browser_screen = FileBrowserController(self)
        self.printing_options_screen = PrintOptionsController(self)
        self.payment_screen = PaymentController(self)
        self.admin_screen = AdminController(self)
        
        self.db_threader.start()
        self.ink_analysis_threader.start()
        
        # Connect thread managers for real-time data updates
        self._connect_thread_managers()
        
        # Initialize printer manager (no dependencies)
        self.printer_manager = PrinterManager()
        
        # Initialize USB file manager for session management

        self.usb_file_manager = USBFileManager()
        print("USB file manager initialized successfully")

        
        # Track low paper alert to prevent multiple SMS
        self.low_paper_alert_sent = False
        
        # Initialize remaining screens that depend on other components
        self.data_viewer_screen = DataViewerController(self, self.admin_screen.db_manager)
        print("Data viewer screen initialized successfully")

            
        self.thank_you_screen = ThankYouController(self)

        # Add all screens to stacked widget in order (see SCREEN_MAP)
        self.stacked_widget.addWidget(self.idle_screen)
        self.stacked_widget.addWidget(self.usb_screen)
        self.stacked_widget.addWidget(self.file_browser_screen)
        self.stacked_widget.addWidget(self.printing_options_screen)
        self.stacked_widget.addWidget(self.payment_screen)
        self.stacked_widget.addWidget(self.admin_screen)
        self.stacked_widget.addWidget(self.data_viewer_screen)
        self.stacked_widget.addWidget(self.thank_you_screen)
        
        # Show idle screen as initial screen
        self.show_screen('idle')
        
        # Connect printer manager signals immediately after initialization
        from PyQt5.QtCore import Qt
        self.printer_manager.print_job_successful.connect(self.on_print_successful, Qt.QueuedConnection)
        self.printer_manager.print_job_failed.connect(self.on_print_failed, Qt.QueuedConnection)
        self.printer_manager.print_job_waiting.connect(self.on_print_waiting, Qt.QueuedConnection)
        
        # Connect payment signals after screens are ready
        self.payment_screen.payment_completed.connect(self.on_payment_completed)
        
        # Signal connection established successfully
        print("Signals established successfully")

        # Apply application-wide styles
        self.setStyleSheet("""
            QMainWindow {
                background-color: transparent;
            }
        """)
    
    def _setup_display(self):
        # Get the geometry of the primary screen
        screen = QApplication.primaryScreen()
        screen_geometry = screen.geometry()
        
        # Move the window to the top-left corner of the screen
        self.move(screen_geometry.topLeft())
        
        # Set the window to the full size of the screen
        # This makes the transition to fullscreen smoother
        self.resize(screen_geometry.size())

        # Set window flags for a true kiosk experience
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        
        # Go fullscreen on startup
        self.showFullScreen()
    
    def _connect_thread_managers(self):
        # Connect ink analysis completion for database updates
        self.ink_analysis_threader.analysis_completed.connect(self._on_ink_analysis_completed)

    
    def _on_ink_analysis_completed(self, result):
        """Handle ink analysis completion - update CMYK levels and clean up temp PDF."""
        try:
            # Handle signal payload (dict from ink_analysis_threader)
            if isinstance(result, dict) and result.get('database_updated', False) and 'cmyk_levels' in result:
                print(f"CMYK levels updated: {result['cmyk_levels']}")
                self.db_threader.cmyk_levels_updated.emit(result['cmyk_levels'])
        finally:
            # Always clean up temp PDF after analysis completes
            self.printer_manager.cleanup_last_temp_pdf()

    def check_paper_count_and_redirect(self, allow_admin_access=False):
        paper_count = self.admin_screen.get_paper_count()
        if paper_count <= 1:
            print(f"Low paper detected: {paper_count} pages remaining. Redirecting to error screen.")
            self.show_screen('thank_you')
            # Show the no paper error on the thank you screen
            self.thank_you_screen.show_no_paper_error(paper_count)
            return True
        return False

    def show_screen(self, screen_name):
        # Call on_leave lifecycle method for current screen
        current_widget = self.stacked_widget.currentWidget()
        if hasattr(current_widget, 'on_leave'):
            current_widget.on_leave()

        # Check paper count before switching to most screens (except admin and thank_you)
        if screen_name not in ['admin', 'thank_you']:
            if self.check_paper_count_and_redirect():
                print(f"Cannot navigate to {screen_name} - insufficient paper")
                return
        
        # Switch to the new screen
        target_index = self.SCREEN_MAP[screen_name]
        self.stacked_widget.setCurrentIndex(target_index)
        
        # Call on_enter lifecycle method for new screen
        new_widget = self.stacked_widget.currentWidget()
        if hasattr(new_widget, 'on_enter'):
            try:
                new_widget.on_enter()
            except Exception as e:
                print(f"ERROR: show_screen - new_widget.on_enter() failed with error: {e}")
                import traceback
                traceback.print_exc()

    def on_payment_completed(self, payment_info):
        # Store payment info for later use in transaction logging and inventory updates
        self.current_payment_info = payment_info
        print(f"Stored payment info: {payment_info}")
        
        # CRITICAL FIX: Update database immediately after payment completion
        # This ensures database is updated even if printing fails
        print(f"Updating database immediately")
        self._update_database_after_payment(payment_info)
        
        # Navigate to thank you screen first (before checking printer)
        print(f"Navigating to thank you screen...")
        self.show_screen('thank_you')
        
        # Verify file exists before printing
        file_path = payment_info['pdf_data']['path']
        print(f"Verifying file before printing: {file_path}")
        
        # Use USB file manager to verify file is in current session
        if hasattr(self, 'usb_file_manager') and self.usb_file_manager:
            if not self.usb_file_manager.verify_file_in_session(file_path):
                print(f"PDF file not found in current session: {file_path}")
                self.thank_you_screen.show_printing_error(f"PDF file not found: {os.path.basename(file_path)}")
                return
        elif not os.path.exists(file_path):
            print(f"PDF file not found: {file_path}")
            self.thank_you_screen.show_printing_error(f"PDF file not found: {os.path.basename(file_path)}")
            return
        
        # Check printer availability before starting print job
        if not self.printer_manager.check_printer_availability():
            print(f"Printer not available")
            self.thank_you_screen.show_printing_error("Printer is not available. Please check printer connection.")
            return
        
        # Store print job details for thank you screen
        self.current_print_job = {
            'file_path': file_path,
            'selected_pages': payment_info['selected_pages'],
            'copies': payment_info['copies'],
            'color_mode': payment_info['color_mode']
        }
        print(f"Print job details stored")
        
        # Start print job
        try:
            self.printer_manager.print_file(
                file_path=file_path,
                copies=payment_info['copies'],
                color_mode=payment_info['color_mode'],
                selected_pages=payment_info['selected_pages']
            )
            print(f"Print job started successfully")
        except Exception as e:
            print(f"Error starting print job: {e}")
            self.thank_you_screen.show_printing_error(f"Failed to start print job: {str(e)}")

    def _update_database_after_payment(self, payment_info):
        try:
            # 1. Log transaction immediately (using PaymentModel)
            if hasattr(self, 'payment_screen') and self.payment_screen:
                self.payment_screen.model.log_transaction(payment_info)
            else:
                print(f"No payment screen available for transaction logging")
            
            # 2. Update coin inventory (add received coins) (using PaymentModel)
            if hasattr(self, 'payment_screen') and self.payment_screen:
                self.payment_screen.model.update_coin_inventory_after_payment()
            else:
                print(f"No payment screen available for coin inventory update")
            
            # Note: Paper count is updated after successful printing, not after payment
            # This ensures paper is only decremented if printing actually succeeds
            
            print(f"Database updated")
            
        except Exception as e:
            print(f"Error updating database: {e}")
            import traceback
            traceback.print_exc()



    def _cleanup_session_directory_after_print(self):
        if hasattr(self, 'usb_file_manager') and self.usb_file_manager:
            self.usb_file_manager.cleanup_session_directory()
        else:
            print(f"No USB file manager available for cleanup")

    def on_print_successful(self):
        print("Print job successfully completed")
        
        # Update paper count after successful printing (before clearing print job)
        self._update_paper_count_after_print()
        
        # Clean up session directory after successful printing
        self._cleanup_session_directory_after_print()
        
        # Trigger ink analysis for the printed job (before clearing print job info)
        self._trigger_ink_analysis()
        
        # Clear the print job after successful completion to prevent re-printing
        self.current_print_job = None
        
        # Note: thank_you screen's _on_print_success() handles the UI update automatically
        # via the print_job_successful signal connection, so no need to call finish_printing() here
        current_screen = self.stacked_widget.currentWidget()
        
        if current_screen == self.idle_screen:
            # Print completed while on idle screen - this is normal, no need to show thank you screen
            print("Print completed while on idle screen - no action needed")
        elif current_screen != self.thank_you_screen:
            # Print job completed but we're on wrong screen - navigate to thank you screen
            print(f"Print completed on wrong screen, navigating to thank you screen")
            self.show_screen('thank_you')

    def _trigger_ink_analysis(self):
        if not hasattr(self, 'current_print_job') or not self.current_print_job:
            print("No print job info available for ink analysis")
            return
        
        # Get the temp PDF path from printer manager
        if not hasattr(self.printer_manager, 'last_temp_pdf_path') or not self.printer_manager.last_temp_pdf_path:
            print("No temp PDF available for ink analysis")
            return
        
        temp_pdf_path = self.printer_manager.last_temp_pdf_path
        
        try:
            # Use temp PDF (already has only selected pages!) instead of original file
            # This works even if USB drive is removed
            # Note: Completion is handled via signal connection in _connect_thread_managers()
            self.ink_analysis_threader.analyze_and_update(
                pdf_path=temp_pdf_path,
                selected_pages=None,  # All pages in temp PDF (already filtered)
                copies=self.current_print_job['copies'],
                dpi=150,
                color_mode=self.current_print_job['color_mode']
            )
        except Exception as e:
            print(f"Error triggering ink analysis: {e}")
            # Clean up temp PDF even if analysis fails
            self.printer_manager.cleanup_last_temp_pdf()
    
    def _update_paper_count_after_print(self):
        """Update paper count after successful printing."""
        if not hasattr(self, 'current_print_job') or not self.current_print_job:
            print("No print job info available for paper count update")
            return
        
        try:
            # Calculate total pages printed
            selected_pages = self.current_print_job.get('selected_pages', [])
            copies = self.current_print_job.get('copies', 1)
            total_pages = len(selected_pages) * copies
            
            print(f"Updating paper count: -{total_pages} pages (pages: {len(selected_pages)}, copies: {copies})")
            
            # Update paper count using AdminModel
            if hasattr(self, 'admin_screen') and self.admin_screen:
                # Get current paper count before update
                current_count = self.admin_screen.get_paper_count()
                
                # Decrement paper count (AdminModel handles the database update and low paper alerts)
                success = self.admin_screen.model.decrement_paper_count(total_pages)
                
                if success:
                    # Get updated count after decrement
                    updated_count = self.admin_screen.get_paper_count()
                    print(f"Paper count updated: {current_count} -> {updated_count}")
                    
                    # Check for low paper alert flag (application-level state management)
                    if updated_count <= 10 and not self.low_paper_alert_sent:
                        print(f"Low paper alert flag set: {updated_count} sheets remaining")
                        self.low_paper_alert_sent = True
                    elif updated_count > 10:
                        # Reset flag if paper count goes back above threshold
                        self.low_paper_alert_sent = False
                else:
                    print("Failed to update paper count")
            else:
                print("No admin screen available for paper count update")
                
        except Exception as e:
            print(f"Error updating paper count: {e}")


    def on_print_waiting(self):
        print("Waiting for print job to complete")
        
        if self.stacked_widget.currentWidget() == self.thank_you_screen:
            self.thank_you_screen.show_waiting_for_print()
        else:
            print(f"Print waiting signal on wrong screen ({type(self.stacked_widget.currentWidget()).__name__})")

    def on_print_failed(self, error_message):
        print(f"Print job failed: {error_message}")
        
        # Clean up session directory after print failure
        self._cleanup_session_directory_after_print()
        
        # Send SMS notification for all print failures
        try:
            from managers.sms_manager import send_printing_error_sms
            send_printing_error_sms(error_message)
        except Exception as sms_error:
            print(f"Failed to send SMS notification: {sms_error}")
        
        # Log error to database
        try:
            from utils.error_logger import log_error
            log_error("Print Job Failed", error_message, "main_app")
        except Exception as db_error:
            print(f"Failed to log error to database: {db_error}")
        
        # Display error on thank you screen
        if self.stacked_widget.currentWidget() == self.thank_you_screen:
            # Check if this is a paper jam error for specialized handling
            if "paper jam" in error_message.lower() or "jam" in error_message.lower():
                self.thank_you_screen.show_paper_jam_error(error_message)
            else:
                self.thank_you_screen.show_printing_error(error_message)
        else:
            print(f"Print failed on wrong screen. Error: {error_message}")

    def cleanup(self):
        try:
            print("Starting application cleanup")
            
            # Stop database operations first to prevent SQLite thread errors
            if hasattr(self, 'db_threader'):
                print("Stopping database threader")
                self.db_threader.stop()
            if hasattr(self, 'ink_analysis_threader'):
                print("Stopping ink analysis threader")
                self.ink_analysis_threader.stop()
            
            # Stop USB monitoring thread
            if hasattr(self, 'usb_screen') and hasattr(self.usb_screen, 'model'):
                print("Stopping USB monitoring")
                self.usb_screen.model.stop_usb_monitoring()
            
            # Clean up database connections before other cleanup
            try:
                from utils.error_logger import cleanup_db_connections
                print("Cleaning up database connections")
                cleanup_db_connections()
            except Exception as db_cleanup_error:
                print(f"Error cleaning up database connections: {db_cleanup_error}")
            
            # Clean up SMS system
            print("Cleaning up SMS system")
            cleanup_sms()
            
            # Clean up persistent GPIO last
            print("Cleaning up persistent GPIO")
            # GPIO threads are cleaned up by individual screens
            
            print("Application cleanup completed")
                
        except Exception as e:
            print(f"Error during cleanup: {e}")

    def closeEvent(self, event):
        self.cleanup()
        event.accept()


def main():
    try:
        print("\nInitializing database...")
        init_db()
        print("Database initialization successful\n")
    
        # Create Qt application
        app = QApplication(sys.argv) # Main thread init
        app.setApplicationName("Printing System GUI")
        app.setApplicationVersion("1.21")
        window = PrintingSystemApp()

        # Show window (size and mode determined by _setup_display)
        window.show()
        
        # Set up cleanup on exit
        import atexit
        from managers.payment_handler import cleanup_payment_handler
        atexit.register(cleanup_payment_handler)
        
        sys.exit(app.exec_())
    except Exception as e:
        print(f"Error during initialization: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()

# Functions in here are for database, file cleaning, or other system-level operations that are not screen-specific.
