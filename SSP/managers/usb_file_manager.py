import os
import shutil
import psutil
import tempfile
import platform
import threading
from datetime import datetime

class USBFileManager:
    def __init__(self):
        # Create a unique session ID and a session-specific temp directory
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_base_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem")
        self.destination_dir = os.path.join(temp_base_dir, f"Session_{self.session_id}")
        
        os.makedirs(self.destination_dir, exist_ok=True)
        print(f"Temp directory created for session {self.session_id}: {self.destination_dir}")

        self.supported_extensions = ['.pdf']
        self.last_known_drives = set()
        
        # Disk safety tracking
        self.current_usb_drive = None
        self.files_in_use = set()  # Track files currently being processed
        self.operation_in_progress = False
        self._should_stop = False  # Flag to stop operations
    
    def _safe_pdf_page_count(self, file_path, timeout=5):
        result = [1]  # Default fallback
        
        def get_page_count():
            try:
                import fitz  # PyMuPDF
                doc = None
                try:
                    doc = fitz.open(file_path)
                    result[0] = len(doc)
                except Exception as pdf_error:
                    print(f"PDF error for {os.path.basename(file_path)}: {pdf_error}")
                    result[0] = 1
                finally:
                    if doc:
                        try:
                            doc.close()
                        except:
                            pass
            except ImportError:
                print(f"PyMuPDF not available for {os.path.basename(file_path)}")
                result[0] = 1
            except Exception as e:
                print(f"Unexpected error processing {os.path.basename(file_path)}: {e}")
                result[0] = 1
        
        # Run in thread with timeout
        thread = threading.Thread(target=get_page_count)
        thread.daemon = True
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            print(f"PDF processing timeout for {os.path.basename(file_path)}, using default page count")
            result[0] = 1
        
        return result[0]
    
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
    
    
    def check_for_new_drives(self):
        current_drives = set(self.get_usb_drives())
        new_drives = current_drives - self.last_known_drives
        removed_drives = self.last_known_drives - current_drives
        
        self.last_known_drives = current_drives
        
        return list(new_drives), list(removed_drives)
    
    def scan_pdf_files(self, source_dir):
        print(f"\nStarting PDF scan for {source_dir}")
        scanned_files = []

        # Reset stop flag for new operation
        self._should_stop = False
        print("Reset stop flag for new USB operation")

        try:
            # Only create a new session directory if we don't have one or if it's a different USB drive
            if not self.destination_dir or not os.path.exists(self.destination_dir) or self.current_usb_drive != source_dir:
                print(f"Creating new session directory for USB drive: {source_dir}")
                self._create_new_session()
            else:
                print(f"Reusing existing session directory: {self.destination_dir}")
            
            # Set current drive and mark operation as in progress
            self.set_current_drive(source_dir)
            self.set_operation_in_progress(True)
            
            print(f"Light scanning PDF files from {source_dir}")
            
            # Limit directory traversal to prevent system load
            max_directories = 5
            directory_count = 0
            
            for root, _, files in os.walk(source_dir):
                if directory_count >= max_directories:
                    print(f"Reached directory limit ({max_directories}), stopping scan")
                    break
                
                directory_count += 1
                
                # Check stop flag during directory traversal
                if self._should_stop:
                    print("Stop requested during file scanning")
                    break
                
                # Limit number of files per directory
                max_files_per_dir = 20
                file_count = 0
                
                for filename in files:
                    if file_count >= max_files_per_dir:
                        print(f"Reached file limit per directory ({max_files_per_dir}), skipping remaining")
                        break
                    
                    if filename.lower().endswith('.pdf'):
                        file_count += 1
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
                            file_size = source_size
                            print(f"Found {filename} ({file_size/1024:.1f} KB)")
                            
                            # Safe PDF page count with timeout (read directly from USB)
                            page_count = self._safe_pdf_page_count(source_path, timeout=3)
                            print(f"{filename}: {page_count} pages")
                            
                            # Store file info without copying
                            scanned_files.append({
                                'filename': filename,
                                'path': source_path,  # Keep original USB path
                                'size': file_size,
                                'pages': page_count,
                                'type': '.pdf'
                            })
                            
                        except Exception as e:
                            print(f"Error processing {filename}: {str(e)}")
                            continue
                            
            # Mark operation as complete
            self.set_operation_in_progress(False)
            
            # After all files are processed
            if scanned_files:
                print(f"Successfully scanned {len(scanned_files)} PDF files:")
                for f in scanned_files:
                    print(f"    Found {f['filename']} ({f['size']/1024:.1f} KB, {f['pages']} pages)")
            else:
                print("No PDF files found")
                
            return scanned_files

        except Exception as e:
            print(f"Error in scan_pdf_files: {str(e)}")
            # Ensure operation is marked as complete even on error
            self.set_operation_in_progress(False)
            return []
    
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
                print(f"Source and destination are the same, skipping copy: {filename}")
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
    
    def stop_all_operations(self):
        try:
            print("Stopping USB file operations...")
            self._should_stop = True
            self.operation_in_progress = False
            print("USB file operations stopped")
        except Exception as e:
            print(f"Error stopping USB operations: {e}")
        
    def cleanup_temp_files(self):
        try:
            if os.path.exists(self.destination_dir):
                print(f"Cleaning up temporary files in {self.destination_dir}")
                
                # Remove all files in the directory
                for filename in os.listdir(self.destination_dir):
                    file_path = os.path.join(self.destination_dir, filename)
                    try:
                        if os.path.isfile(file_path):
                            os.remove(file_path)
                            print(f"Deleted: {filename}")
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                            print(f"Deleted directory: {filename}")
                    except Exception as e:
                        print(f"Error deleting {filename}: {e}")
                
                print("Temporary files cleanup completed")
            else:
                print("Temporary directory does not exist")
                
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
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
    
    def get_temp_folder_info(self):
        try:
            if os.path.exists(self.destination_dir):
                files = os.listdir(self.destination_dir)
                total_size = 0
                for filename in files:
                    file_path = os.path.join(self.destination_dir, filename)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
                
                return {
                    'folder_path': self.destination_dir,
                    'file_count': len(files),
                    'total_size': total_size,
                    'session_id': self.session_id # This will now work
                }
            else:
                return None
        except Exception as e:
            print(f"Error getting temp folder info: {e}")
            return None
    

    
    def set_current_drive(self, drive_path):
        self.current_usb_drive = drive_path
        print(f"Set current USB drive: {drive_path}")
    
    def is_drive_safe_to_remove(self):
        if not self.current_usb_drive:
            return True, "No USB drive currently in use"
        
        if self.operation_in_progress:
            return False, "File operations are currently in progress"
        
        if self.files_in_use:
            return False, f"Files are currently being processed: {list(self.files_in_use)}"
        
        # Check if drive is still accessible
        try:
            if not os.path.exists(self.current_usb_drive):
                return False, "USB drive is no longer accessible"
            
            # Try to access the drive
            os.listdir(self.current_usb_drive)
            return True, "USB drive is safe to remove"
        except Exception as e:
            return False, f"USB drive access error: {e}"
    
    def mark_file_in_use(self, file_path):
        self.files_in_use.add(file_path)
        print(f"Marked file as in use: {file_path}")
    
    def mark_file_complete(self, file_path):
        self.files_in_use.discard(file_path)
        print(f"Marked file as complete: {file_path}")
    
    def set_operation_in_progress(self, in_progress):
        self.operation_in_progress = in_progress
        status = "started" if in_progress else "completed"
        print(f"File operation {status}")
    
    def get_safety_warning(self):
        if not self.current_usb_drive:
            return None
        
        is_safe, message = self.is_drive_safe_to_remove()
        if is_safe:
            return None
        
        return f"DO NOT REMOVE USB DRIVE: {message}"
    
    def force_safe_eject(self):
        print("Force safe ejection requested")
        self.files_in_use.clear()
        self.operation_in_progress = False
        self.current_usb_drive = None
        print("USB drive marked as safe to remove")
    
    def force_cleanup_all_resources(self):
        try:
            print("Force cleaning up all USB file manager resources...")
            
            # Clear all tracking data
            self.files_in_use.clear()
            self.operation_in_progress = False
            self.current_usb_drive = None
            self.last_known_drives.clear()
            
            # Clean up all temporary directories (old sessions only)
            self.cleanup_all_temp_folders()
            
            # DO NOT delete current session directory - files are still needed by file browser
            # The current session directory will be cleaned up when the print job is complete
            print(f"Preserving current session directory: {self.destination_dir}")
            
            print("Force cleanup of all resources completed")
            
        except Exception as e:
            print(f"Error during force cleanup: {e}")
            # Log error for debugging
            try:
                from utils.error_logger import log_error
                log_error("USB Force Cleanup All Resources Error", str(e), "usb_file_manager")
            except Exception as log_error:
                print(f"Failed to log error: {log_error}")
    
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
    
    def get_current_session_directory(self):
        return self.destination_dir
    
    def get_current_session_id(self):
        return self.session_id
    
    def cleanup_session_directory(self):
        try:
            session_dir = self.get_current_session_directory()
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
    
    def _auto_eject_usb_drive(self, usb_path):
        try:
            print(f"Auto-ejecting USB drive: {usb_path}")
            
            # Clear all safety tracking
            self.files_in_use.clear()
            self.operation_in_progress = False
            self.current_usb_drive = None
            
            # Try to unmount the drive (Linux only)
            if platform.system() == "Linux":
                try:
                    import subprocess
                    # Find the device path for the mount point
                    result = subprocess.run(['findmnt', '-n', '-o', 'SOURCE', usb_path], 
                                          capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        device = result.stdout.strip()
                        print(f"Unmounting device: {device}")
                        # Use sudo to ensure unmount works
                        unmount_result = subprocess.run(['sudo', 'umount', usb_path], 
                                                       capture_output=True, text=True, timeout=10)
                        if unmount_result.returncode == 0:
                            print(f"USB drive unmounted successfully")
                        else:
                            print(f"Failed to unmount USB drive: {unmount_result.stderr}")
                    else:
                        print("Could not find device for unmounting")
                except Exception as e:
                    print(f"Could not unmount USB drive: {e}")
            
            print("USB drive is now safe to remove at any time")
            
        except Exception as e:
            print(f"Error during auto-eject: {e}")
            # Still clear the safety tracking even if unmount fails
            self.files_in_use.clear()
            self.operation_in_progress = False
            self.current_usb_drive = None