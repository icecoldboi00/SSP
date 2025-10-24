# screens/usb/controller.py

import time
from PyQt5.QtWidgets import QWidget, QGridLayout, QMessageBox
from PyQt5.QtCore import QTimer

from .model import USBScreenModel
from .view import USBScreenView

class USBController(QWidget):
    """Manages the USB screen's logic and UI."""
    
    def __init__(self, main_app, parent=None):
        super().__init__(parent)
        self.main_app = main_app
        
        self.model = USBScreenModel()
        self.view = USBScreenView()
        
        # Setup timeout timer (5 minutes = 300000ms)
        self.timeout_timer = QTimer()
        self.timeout_timer.setSingleShot(True)
        self.timeout_timer.timeout.connect(self._on_timeout)
        
        # Setup watchdog timer to prevent complete freezes
        self.watchdog_timer = QTimer()
        self.watchdog_timer.timeout.connect(self._watchdog_check)
        self.last_activity_time = 0
        
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, 0, 0)
        
        self._connect_signals()
    
    def _connect_signals(self):
        """Connect signals from the view to the model and vice-versa."""
        # --- View -> Controller ---
        self.view.back_button_clicked.connect(self._go_back)
        # Reset timeout on user interaction
        self.view.back_button_clicked.connect(self._reset_timeout)
        
        # --- Model -> View ---
        self.model.status_changed.connect(self._update_status)
        self.model.status_changed.connect(self._update_activity)  # Track activity
        self.model.usb_detected.connect(self.model.on_usb_detected)
        self.model.usb_detected.connect(self._update_activity)  # Track activity
        self.model.usb_removed.connect(self.model.on_usb_removed)
        self.model.usb_removed.connect(self._update_activity)  # Track activity
        self.model.pdf_files_found.connect(self._handle_pdf_files_found)
        self.model.pdf_files_found.connect(self._update_activity)  # Track activity
        self.model.show_message.connect(self.view.show_message)
        
        # Safety warning connections
        self.model.safety_warning.connect(self.view.show_safety_warning)
        self.model.safety_warning_cleared.connect(self.view.hide_safety_warning)
    
    def _update_status(self, text, style_key):
        """Updates the status indicator with the given text and style."""
        color_hex = self.model.get_status_color(style_key)
        self.view.update_status_indicator(text, style_key, color_hex)
    
    
    def _handle_pdf_files_found(self, pdf_files):
        """Handles when PDF files are found on the USB drive."""
        self.main_app.file_browser_screen.load_pdf_files(pdf_files)
        self.main_app.show_screen('file_browser')
    
    def _go_back(self):
        """Navigates back to the idle screen."""
        self.main_app.show_screen('idle')
    
    # --- Public API for main_app ---
    
    def on_enter(self):
        """Called by main_app when this screen becomes active."""
        try:
            print("🔄 Entering USB screen, performing initial check...")
            
            # Check system resources before proceeding
            if not self._check_system_resources():
                print("⚠️ System resources low, performing cleanup...")
                self.model.force_cleanup()
            
            self.view.start_blinking()
            
            # Reset the returning flag when entering normally
            self.model.set_returning_from_file_browser(False)
            
            # Reset USB manager state for new session
            self.model.reset_usb_manager_state()
            
            self.model.check_current_drives()
            
            # Start timeout timer (5 minutes)
            self.timeout_timer.start(300000)
            print("⏰ USB screen timeout started (5 minutes)")
            
            # Start watchdog timer (check every 5 seconds for faster detection)
            self.watchdog_timer.start(5000)
            self.last_activity_time = time.time()
            self.system_check_count = 0
            print("🐕 Watchdog timer started")
            
        except Exception as e:
            print(f"❌ Error entering USB screen: {e}")
            # Log error for debugging
            try:
                from utils.error_logger import log_error
                log_error("USB Screen Enter Error", str(e), "usb_controller")
            except Exception as log_error:
                print(f"⚠️ Failed to log error: {log_error}")
            
            # Show error to user and return to idle
            self.main_app.show_screen('idle')
    
    def on_leave(self):
        """Called by main_app when leaving this screen."""
        try:
            print("⏹️ Leaving USB screen")
            self.model.stop_usb_monitoring()
            self.view.stop_blinking()
            
            # Stop timeout timer
            self.timeout_timer.stop()
            
            # Stop watchdog timer
            self.watchdog_timer.stop()
            print("🐕 Watchdog timer stopped")
            
            # Force cleanup of any remaining resources
            self.model.force_cleanup()
            
        except Exception as e:
            print(f"⚠️ Error leaving USB screen: {e}")
            # Log error for debugging
            try:
                from utils.error_logger import log_error
                log_error("USB Screen Leave Error", str(e), "usb_controller")
            except Exception as log_error:
                print(f"⚠️ Failed to log error: {log_error}")
    
    def _on_timeout(self):
        """Handle timeout - return to idle screen."""
        print("⏰ USB screen timeout - returning to idle screen")
        self.main_app.show_screen('idle')
    
    def _reset_timeout(self):
        """Reset the timeout timer (call on user activity)."""
        self.timeout_timer.stop()
        self.timeout_timer.start(300000)
        print("⏰ USB screen timeout reset")
    
    def reset_usb_state(self):
        """Public method to reset USB monitoring state."""
        self.model.reset_usb_state()
    
    def _check_system_resources(self):
        """Check if system has sufficient resources to proceed with aggressive limits."""
        try:
            import psutil
            import gc
            
            # Force garbage collection first
            gc.collect()
            
            # Check available memory (increased requirement to 200MB)
            memory = psutil.virtual_memory()
            free_memory_mb = memory.available / (1024 * 1024)
            memory_percent = memory.percent
            
            if free_memory_mb < 200:
                print(f"⚠️ CRITICAL: Low memory: {free_memory_mb:.1f}MB available ({memory_percent}% used)")
                self._emergency_cleanup()
                return False
            
            if memory_percent > 85:
                print(f"⚠️ CRITICAL: High memory usage: {memory_percent}%")
                self._emergency_cleanup()
                return False
            
            # Check disk space (increased requirement to 1GB)
            disk = psutil.disk_usage('/')
            free_disk_mb = disk.free / (1024 * 1024)
            
            if free_disk_mb < 1000:
                print(f"⚠️ CRITICAL: Low disk space: {free_disk_mb:.1f}MB available")
                self._emergency_cleanup()
                return False
            
            # Check CPU usage (reduced threshold to 80%)
            cpu_percent = psutil.cpu_percent(interval=0.5)  # Faster check
            if cpu_percent > 80:
                print(f"⚠️ CRITICAL: High CPU usage: {cpu_percent}%")
                self._emergency_cleanup()
                return False
            
            # Check for too many open files
            process = psutil.Process()
            open_files = len(process.open_files())
            if open_files > 100:
                print(f"⚠️ CRITICAL: Too many open files: {open_files}")
                self._emergency_cleanup()
                return False
            
            print(f"✅ System resources OK - Memory: {free_memory_mb:.1f}MB ({memory_percent}%), Disk: {free_disk_mb:.1f}MB, CPU: {cpu_percent}%, Files: {open_files}")
            return True
            
        except Exception as e:
            print(f"⚠️ Error checking system resources: {e}")
            # If we can't check resources, assume they're OK but log the error
            try:
                from utils.error_logger import log_error
                log_error("System Resource Check Error", str(e), "usb_controller")
            except Exception as log_error:
                print(f"⚠️ Failed to log error: {log_error}")
            return True  # Assume OK if we can't check
    
    def _emergency_cleanup(self):
        """Emergency cleanup to free system resources."""
        try:
            print("🚨 EMERGENCY: Performing aggressive cleanup...")
            
            # Force garbage collection
            import gc
            gc.collect()
            
            # Stop any ongoing operations
            if hasattr(self.model, 'usb_manager') and self.model.usb_manager:
                self.model.usb_manager.stop_copy_operation()
                self.model.usb_manager.set_operation_in_progress(False)
            
            # Stop USB monitoring
            self.model.stop_usb_monitoring()
            
            # Clear any cached data
            if hasattr(self.model, 'usb_manager'):
                self.model.usb_manager.force_cleanup_all_resources()
            
            # Force another garbage collection
            gc.collect()
            
            print("✅ Emergency cleanup completed")
            
        except Exception as e:
            print(f"❌ Emergency cleanup failed: {e}")
            # Last resort: restart the application
            self._emergency_restart()
    
    def _emergency_restart(self):
        """Emergency restart of the application."""
        try:
            print("🚨 EMERGENCY: Restarting application...")
            import subprocess
            import sys
            import os
            
            # Kill the current process and restart
            subprocess.Popen([sys.executable, os.path.abspath(__file__)])
            sys.exit(1)
            
        except Exception as e:
            print(f"❌ Emergency restart failed: {e}")
            # Absolute last resort: system reboot
            try:
                import subprocess
                subprocess.run(['sudo', 'reboot'], timeout=10)
            except:
                pass
    
    def _watchdog_check(self):
        """Aggressive watchdog timer to detect and prevent system freezes."""
        try:
            current_time = time.time()
            self.system_check_count += 1
            
            # Check system resources every 5 checks (25 seconds)
            if self.system_check_count % 5 == 0:
                if not self._check_system_resources():
                    print("🐕 Watchdog: System resources critical, forcing cleanup...")
                    self._emergency_cleanup()
                    return
                
                # Also check system responsiveness
                if not self._check_system_responsiveness():
                    print("🐕 Watchdog: System responsiveness critical, emergency restart...")
                    return
            
            # Check if we've been stuck for more than 15 seconds (reduced from 30)
            if current_time - self.last_activity_time > 15:
                print("🐕 Watchdog: No activity for 15+ seconds, checking for freeze...")
                
                # Check if USB manager is stuck
                if hasattr(self.model, 'usb_manager') and self.model.usb_manager:
                    if self.model.usb_manager.operation_in_progress:
                        print("🐕 Watchdog: USB operation appears stuck, attempting recovery...")
                        self._recover_from_freeze()
                    else:
                        # Update activity time if operation is not stuck
                        self.last_activity_time = current_time
                else:
                    # Update activity time if no USB manager
                    self.last_activity_time = current_time
            else:
                # Update activity time on normal operation
                self.last_activity_time = current_time
                
        except Exception as e:
            print(f"🐕 Watchdog error: {e}")
            # If watchdog itself fails, it's a critical system issue
            self._emergency_cleanup()
    
    def _recover_from_freeze(self):
        """Attempt to recover from a freeze."""
        try:
            print("🔄 Attempting to recover from freeze...")
            
            # Stop any ongoing operations
            if hasattr(self.model, 'usb_manager') and self.model.usb_manager:
                self.model.usb_manager.stop_copy_operation()
                self.model.usb_manager.set_operation_in_progress(False)
            
            # Reset USB monitoring
            self.model.stop_usb_monitoring()
            time.sleep(1)  # Give it a moment
            self.model.start_usb_monitoring()
            
            # Update status
            self.model.status_changed.emit("System recovered from freeze. Please try again.", 'warning')
            print("✅ Recovery attempt completed")
            
        except Exception as e:
            print(f"❌ Recovery failed: {e}")
            # Last resort: return to idle screen
            self.main_app.show_screen('idle')
    
    def _update_activity(self):
        """Update the last activity time."""
        self.last_activity_time = time.time()
    
    def _check_system_responsiveness(self):
        """Check if the entire system is becoming unresponsive."""
        try:
            import psutil
            import os
            
            # Check if we can still access system resources
            current_process = psutil.Process()
            
            # Check if process is still responsive
            try:
                cpu_percent = current_process.cpu_percent()
                memory_info = current_process.memory_info()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                print("🐕 CRITICAL: Process appears to be dead or inaccessible")
                self._emergency_restart()
                return False
            
            # Check system load
            try:
                load_avg = os.getloadavg()
                if load_avg[0] > 4.0:  # High system load
                    print(f"🐕 CRITICAL: High system load: {load_avg[0]}")
                    self._emergency_cleanup()
                    return False
            except:
                pass  # getloadavg might not be available on all systems
            
            # Check if we can still write to disk
            try:
                test_file = "/tmp/usb_system_test"
                with open(test_file, 'w') as f:
                    f.write("test")
                os.remove(test_file)
            except Exception as e:
                print(f"🐕 CRITICAL: Cannot write to disk: {e}")
                self._emergency_restart()
                return False
            
            return True
            
        except Exception as e:
            print(f"🐕 CRITICAL: System responsiveness check failed: {e}")
            self._emergency_restart()
            return False