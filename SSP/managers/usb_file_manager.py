import os
import shutil
import psutil
import tempfile
import platform
import threading
import fitz
from datetime import datetime
import re
import subprocess

class USBFileManager:
    def __init__(self):
        # Create a unique session ID and a session-specific temp directory
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_base_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem")
        self.destination_dir = os.path.join(temp_base_dir, f"Session_{self.session_id}")
        
        os.makedirs(self.destination_dir, exist_ok=True) # Create the session directory
        print(f"Temp directory created for session {self.session_id}: {self.destination_dir}")

        self.supported_extensions = ['.pdf']
        self.last_known_drives = set()
        
        # Disk safety tracking
        self.current_usb_drive = None # One drive only at a time
        self.files_in_use = set()  # Track files currently being processed
        self.operation_in_progress = False 
        self._should_stop = False  # Flag to stop operations
    
    # ========================================================================================================================
    # USB SCREEN FUNCTIONS
    # ========================================================================================================================
    
    # Logic for getting usb drives used in usb monitoring
    def get_usb_drives(self):
        usb_drives = []
        
        try:
            partitions = psutil.disk_partitions()
            
            # Limit number of partitions to check to prevent system load
            max_partitions = 5
            checked_count = 0
            
            for partition in partitions:
                if checked_count >= max_partitions:
                    print(f"Reached partition limit ({max_partitions}), stopping scan")
                    break
                
                checked_count += 1
                
                # Check for typical USB mount points
                usb_mount_patterns = [
                    '/media/',
                    '/mnt/',
                    '/run/media/',
                    '/Volumes/'  # Sometimes used on Linux too
                ]
                
                is_usb_mount = any(partition.mountpoint.startswith(pattern) 
                                 for pattern in usb_mount_patterns)
                
                # Also check if explicitly marked as removable
                is_removable = 'removable' in partition.opts
                
                if is_usb_mount or is_removable:
                    try:
                        if os.path.exists(partition.mountpoint) and os.path.isdir(partition.mountpoint):
                            # Light access check - no heavy operations
                            usb_drives.append(partition.mountpoint)
                            print(f"Found USB drive: {partition.mountpoint} ({partition.fstype})")
                    except (OSError, PermissionError):
                        print(f"USB drive {partition.mountpoint} not accessible")
                        
        except Exception as e:
            print(f"Error detecting USB drives: {e}")
        
        print(f"Detected {len(usb_drives)} actual USB drives: {usb_drives}")
        return usb_drives
    
    # Check for new and removed drives used in usb monitoring
    def check_for_new_drives(self):
        current_drives = set(self.get_usb_drives())
        new_drives = current_drives - self.last_known_drives
        removed_drives = self.last_known_drives - current_drives
        
        self.last_known_drives = current_drives
        
        return list(new_drives), list(removed_drives)
    
    # Used to scan called in usb model
    def scan_pdf_files(self, drive_path):
        scanned_files = []

        # Reset stop flag for new operation
        self._should_stop = False

        try:
            # Only create a new session directory if we don't have one or if it's a different USB drive, since data is saved in session when back is clicked
            if not self.destination_dir or not os.path.exists(self.destination_dir) or self.current_usb_drive != drive_path:
                print(f"Creating new session directory for USB drive: {drive_path}")
                self._create_new_session()
            else:
                print(f"Reusing existing session directory: {self.destination_dir}")
            
            # Set current drive and mark operation as in progress
            self.current_usb_drive = drive_path
            print(f"Set current USB drive: {drive_path}")
            self.operation_in_progress = True
                       
            # Limit total number of files processed to prevent system load,
            # but still allow scanning nested folders (previous directory cap skipped subfolders)
            max_total_files = 200
            total_files_processed = 0
            
            for root, _, files in os.walk(drive_path):
                if self._should_stop:
                    print("USB scan stopped by request")
                    break
                
                if total_files_processed >= max_total_files:
                    print(f"Reached total file limit ({max_total_files}), stopping scan")
                    break
                
                # Limit number of files per directory
                max_files_per_dir = 30
                file_count = 0
                
                for filename in files:
                    if file_count >= max_files_per_dir:
                        print(f"Reached file limit per directory ({max_files_per_dir}), skipping remaining")
                        break
                    
                    if filename.lower().endswith('.pdf'):
                        file_count += 1
                        total_files_processed += 1
                        source_path = os.path.join(root, filename)
                        
                        # Check file size to prevent memory issues
                        try:
                            source_size = os.path.getsize(source_path)
                            if source_size > 50 * 1024 * 1024:  # 50MB limit
                                print(f"Skipping large file {filename} ({source_size/1024/1024:.1f} MB)")
                                continue
                        except Exception as size_error:
                            print(f"Could not check size of {filename}: {size_error}")
                            continue
                        
                        try:
                            # Get file info without copying
                            print(f"Found {filename} ({source_size/1024:.1f} KB)")
                            
                            # Safe PDF page count with timeout (read directly from USB)
                            page_count = self._safe_pdf_page_count(source_path, timeout=3)
                            print(f"{filename}: {page_count} pages")
                            
                            # Store file info without copying
                            scanned_files.append({
                                'filename': filename,
                                'path': source_path,  # Original USB path
                                'pages': page_count,
                                'type': '.pdf'
                            })
                            
                        except Exception as e:
                            print(f"Error processing {filename}: {str(e)}")
                            continue
                
                if total_files_processed >= max_total_files:
                    print(f"Total file limit reached ({max_total_files}), exiting scan loop")
                    break
                            
            # Mark operation as complete
            self.operation_in_progress = False
            
            return scanned_files # Return list of dictionaries 

        except Exception as e:
            print(f"Error in scan_pdf_files: {str(e)}")
            # Ensure operation is marked as complete even on error
            self.operation_in_progress = False
            return []

    # Called in usb timeout
    def stop_all_operations(self):
        try:
            self._should_stop = True
            self.operation_in_progress = False
            print("USB file operations stopped")
        except Exception as e:
            print(f"Error stopping USB operations: {e}")

    # Called on leaving usb screen but doesn't remove session directory (cleaned later in ty)
    def cleanup_all_resources(self):
        try:  
            # Clear all tracking data
            self.files_in_use.clear()
            self.operation_in_progress = False
            self.last_known_drives.clear()
            
            # Clean up all temporary directories (old sessions only)
            self.cleanup_all_temp_folders()
               
            print("Cleanup of all resources completed, session directory saved")
            
        except Exception as e:
            print(f"Error during cleanup: {e}")

    # ========================================================================================================================
    # FILE BROWSER SCREEN FUNCTIONS
    # ========================================================================================================================
    
    def copy_selected_file(self, file_info):
        try:
            # Defensive copy; never mutate caller's dict
            result_info = dict(file_info) if isinstance(file_info, dict) else None
            if not result_info or 'path' not in result_info or 'filename' not in result_info:
                print("Invalid file info provided to copy_selected_file")
                return None

            source_path = result_info['path']
            filename = result_info['filename']

            # Ensure we have a session directory
            if not hasattr(self, 'destination_dir') or not self.destination_dir:
                self._create_new_session()

            # If the file already resides within the current session dir and exists, skip copying
            if isinstance(source_path, str) and source_path.startswith(self.destination_dir) and os.path.exists(source_path):
                print(f"File already in session directory, skipping copy: {filename}")
                return result_info

            dest_path = os.path.join(self.destination_dir, filename)

            # If destination is the same as source, skip copying
            if os.path.abspath(dest_path) == os.path.abspath(source_path):
                return result_info

            # Ensure destination directory exists
            os.makedirs(self.destination_dir, exist_ok=True)

            print(f"Copying selected file: {filename}")
            try:
                shutil.copy2(source_path, dest_path)
            except shutil.SameFileError:
                print(f"Same file detected during copy, skipping: {filename}")
                return result_info

            if os.path.exists(dest_path):
                file_size = os.path.getsize(dest_path)
                print(f"Copied {filename} ({file_size/1024:.1f} KB)")
                # Return new dict with updated path
                result_info['path'] = dest_path
                return result_info
            else:
                print(f"Failed to copy {filename}")
                return None

        except Exception as e:
            print(f"Error copying selected file: {e}")
            return None

    def verify_file_in_session(self, file_path):
        if not file_path:
            return False
        
        # Check if file exists
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return False
        
        # Check if file is in current session directory
        if not file_path.startswith(self.destination_dir):
            print(f"File is not in current session directory: {file_path}")
            print(f"Expected to be in: {self.destination_dir}")
            return False
        
        print(f"File verified in session directory: {file_path}")
        return True

    def mark_file_in_use(self, file_path):
        self.files_in_use.add(file_path)
        print(f"Marked file as in use: {file_path}")
    
    def mark_file_complete(self, file_path):
        self.files_in_use.discard(file_path)
        print(f"Marked file as complete: {file_path}")

    # ========================================================================================================================
    # SHARED FUNCTIONS USB Screen & Thank you ; main_app.py
    # ========================================================================================================================
    
    def cleanup_all_temp_folders(self):
        try:
            # FIX: Use the correct base directory
            temp_base_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem")
            if os.path.exists(temp_base_dir):
                print(f"Cleaning up old session folders in {temp_base_dir}")
            
                current_session_folder = f"Session_{self.session_id}"
                cleaned_count = 0
            
                for folder_name in os.listdir(temp_base_dir):
                    if folder_name.startswith("Session_") and folder_name != current_session_folder:
                        folder_path = os.path.join(temp_base_dir, folder_name)
                        try:
                            if os.path.isdir(folder_path):
                                shutil.rmtree(folder_path)
                                print(f"Deleted old session folder: {folder_name}")
                                cleaned_count += 1
                        except Exception as e:
                            print(f"Error deleting old session folder {folder_name}: {e}")
                
                print(f"Cleaned up {cleaned_count} old session folders")
                        
        except Exception as e:
            print(f"Error cleaning up old session folders: {e}")
            # Log error for debugging
            try:
                from utils.error_logger import log_error
                log_error("USB Temp Folder Cleanup Error", str(e), "usb_file_manager")
            except Exception as log_error:
                print(f"Failed to log error: {log_error}")

    # Must be done last, called in main app
    def cleanup_session_directory(self):
        try:
            session_dir = self.destination_dir
            if session_dir and os.path.exists(session_dir):
                shutil.rmtree(session_dir)
                print(f"Session directory cleaned up: {session_dir}")
                return True
            else:
                print(f"No session directory to clean up")
                return False
        except Exception as e:
            print(f"Error cleaning up session directory: {e}")
            return False


    # ========================================================================================================================
    # INTERNAL/HELPER FUNCTIONS
    # ========================================================================================================================
    
    def _safe_pdf_page_count(self, file_path, timeout=5):
        def _open_and_count():
            try:
                with fitz.open(file_path) as doc:
                    return len(doc)
            except Exception as pdf_error:
                print(f"PDF error for {os.path.basename(file_path)}: {pdf_error}")
                return 1

        result = [1]  # Default fallback

        def worker():
            try:
                result[0] = _open_and_count()
            except Exception as e:
                print(f"Unexpected error processing {os.path.basename(file_path)}: {e}")
                result[0] = 1
        
        # Run in thread with timeout
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            print(f"PDF processing timeout for {os.path.basename(file_path)}, using default page count")
            result[0] = 1
        
        return result[0]

    def _create_new_session(self):
        # Generate new session ID with current timestamp
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_base_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem")
        self.destination_dir = os.path.join(temp_base_dir, f"Session_{self.session_id}")
        
        # Create the new directory
        os.makedirs(self.destination_dir, exist_ok=True)
        print(f"New session directory created: {self.destination_dir}")
        
        # Clear any previous session data
        self.files_in_use.clear()
        self.operation_in_progress = False
        self.current_usb_drive = None



    # ========================================================================================================================
    # THANK YOU SCREEN FUNCTIONS
    # ========================================================================================================================
    
    def eject_current_usb_drive(self):
        usb_path = self.current_usb_drive
        if not usb_path:
            print("No current USB drive to eject")
            return False

        try:
            print(f"Auto-ejecting USB drive: {usb_path}")

            # Clear all safety tracking first so our app won't touch this drive again
            self.files_in_use.clear()
            self.operation_in_progress = False

            # Try to unmount + power-off (Linux only). This matches what the file manager "Eject" menu does.
            if platform.system() == "Linux":
                try:
                    # Resolve mountpoint -> partition device (e.g. /dev/sdb1)
                    result = subprocess.run(
                        ['findmnt', '-n', '-o', 'SOURCE', '--target', usb_path],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        part_dev = result.stdout.strip()
                        print(f"Resolved mount to device: {part_dev}")

                        # Prefer udisksctl (Eject menu behavior). Try without sudo first, then sudo -n.
                        unmount_cmds = [
                            ['udisksctl', 'unmount', '-b', part_dev],
                            ['sudo', '-n', 'udisksctl', 'unmount', '-b', part_dev],
                        ]
                        unmounted = False
                        last_err = ""
                        for cmd in unmount_cmds:
                            r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                            if r.returncode == 0:
                                unmounted = True
                                if r.stdout.strip():
                                    print(r.stdout.strip())
                                break
                            last_err = (r.stderr or r.stdout or "").strip()

                        # Fallback: plain umount (try without sudo then sudo -n)
                        if not unmounted:
                            print(f"udisksctl unmount failed: {last_err}")
                            for cmd in (['umount', usb_path], ['sudo', '-n', 'umount', usb_path]):
                                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                                if r.returncode == 0:
                                    unmounted = True
                                    break

                        powered_off = False
                        if unmounted:
                            # Determine parent device for power-off (e.g. /dev/sdb)
                            parent = None
                            r = subprocess.run(['lsblk', '-no', 'PKNAME', part_dev], capture_output=True, text=True, timeout=5)
                            if r.returncode == 0 and r.stdout.strip():
                                parent = '/dev/' + r.stdout.strip()
                            else:
                                parent = re.sub(r'(\d+)$', '', part_dev)

                            if parent and parent.startswith('/dev/'):
                                power_cmds = [
                                    ['udisksctl', 'power-off', '-b', parent],
                                    ['sudo', '-n', 'udisksctl', 'power-off', '-b', parent],
                                ]
                                last_err = ""
                                for cmd in power_cmds:
                                    r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                                    if r.returncode == 0:
                                        powered_off = True
                                        if r.stdout.strip():
                                            print(r.stdout.strip())
                                        break
                                    last_err = (r.stderr or r.stdout or "").strip()

                                if not powered_off:
                                    print(f"udisksctl power-off failed: {last_err}")
                            else:
                                print(f"Could not determine parent device for power-off (part={part_dev})")

                            print("USB drive unmounted successfully")
                            if powered_off:
                                print("USB drive powered off successfully (menu eject)")
                        else:
                            print("USB eject failed: could not unmount")
                            return False
                    else:
                        print(f"Could not resolve device for mountpoint '{usb_path}': {(result.stderr or '').strip()}")
                        return False
                except Exception as e:
                    print(f"Could not unmount USB drive: {e}")
                    return False
            else:
                print(f"USB eject requested on unsupported platform ({platform.system()}); treating as safe to remove")

            print("USB drive is now safe to remove at any time")
            return True
        except Exception as e:
            print(f"Error during auto-eject: {e}")
            return False
        finally:
            # Always clear the pointer to the current drive
            self.current_usb_drive = None

