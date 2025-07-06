import os
import shutil
import psutil
import tempfile
import platform
from datetime import datetime

class USBFileManager:
    """Handles USB detection and PDF file filtering"""
    
    def __init__(self):
        # Create a temporary folder for this session
        self.temp_base_dir = os.path.join(tempfile.gettempdir(), "PrintingSystem")
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.destination_dir = os.path.join(self.temp_base_dir, f"Session_{self.session_id}")
        
        self.supported_extensions = ['.pdf']
        self.last_known_drives = set()
        
        # Create the destination directory
        if not os.path.exists(self.destination_dir):
            os.makedirs(self.destination_dir)
            
        print(f"USBFileManager initialized with destination: {self.destination_dir}")
    
    def get_usb_drives(self):
        """Detect ONLY actual USB/removable drives - exclude all internal drives"""
        usb_drives = []
        system = platform.system()
        
        try:
            if system == "Windows":
                usb_drives = self._get_windows_usb_drives()
            elif system == "Linux":
                usb_drives = self._get_linux_usb_drives()
            elif system == "Darwin":  # macOS
                usb_drives = self._get_macos_usb_drives()
            else:
                print(f"Unsupported operating system: {system}")
                
        except Exception as e:
            print(f"Error detecting USB drives: {e}")
        
        print(f"Detected {len(usb_drives)} actual USB drives: {usb_drives}")
        return usb_drives
    
    def _get_windows_usb_drives(self):
        """Windows-specific USB drive detection"""
        usb_drives = []
        
        try:
            import win32file
            import win32api
            
            # Get all logical drives
            drives = win32api.GetLogicalDriveStrings()
            drives = drives.split('\000')[:-1]
            
            for drive in drives:
                try:
                    # Check if it's a removable drive
                    drive_type = win32file.GetDriveType(drive)
                    
                    # DRIVE_REMOVABLE = 2 (floppy, USB, etc.)
                    if drive_type == 2:
                        # Additional check to ensure it's accessible
                        if os.path.exists(drive) and os.path.isdir(drive):
                            try:
                                # Try to access the drive to make sure it's ready
                                os.listdir(drive)
                                usb_drives.append(drive)
                                print(f"Found removable USB drive: {drive}")
                            except (OSError, PermissionError):
                                print(f"USB drive {drive} not ready or accessible")
                                
                except Exception as e:
                    print(f"Error checking drive {drive}: {e}")
                    continue
                    
        except ImportError:
            print("pywin32 not available, using fallback method")
            # Fallback method using psutil
            usb_drives = self._get_usb_drives_fallback()
            
        return usb_drives
    
    def _get_linux_usb_drives(self):
        """Linux-specific USB drive detection"""
        usb_drives = []
        
        try:
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
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
                            # Try to access to ensure it's ready
                            os.listdir(partition.mountpoint)
                            usb_drives.append(partition.mountpoint)
                            print(f"Found USB drive: {partition.mountpoint} ({partition.fstype})")
                    except (OSError, PermissionError):
                        print(f"USB drive {partition.mountpoint} not accessible")
                        
        except Exception as e:
            print(f"Error in Linux USB detection: {e}")
            
        return usb_drives
    
    def _get_macos_usb_drives(self):
        """macOS-specific USB drive detection"""
        usb_drives = []
        
        try:
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                # On macOS, USB drives are typically mounted under /Volumes/
                if partition.mountpoint.startswith('/Volumes/'):
                    # Skip the main system volume
                    if partition.mountpoint != '/Volumes/Macintosh HD':
                        try:
                            if os.path.exists(partition.mountpoint) and os.path.isdir(partition.mountpoint):
                                os.listdir(partition.mountpoint)
                                usb_drives.append(partition.mountpoint)
                                print(f"Found USB drive: {partition.mountpoint}")
                        except (OSError, PermissionError):
                            print(f"USB drive {partition.mountpoint} not accessible")
                            
        except Exception as e:
            print(f"Error in macOS USB detection: {e}")
            
        return usb_drives
    
    def _get_usb_drives_fallback(self):
        """Fallback method for USB detection"""
        usb_drives = []
        
        try:
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                # Only check drives that are explicitly marked as removable
                if 'removable' in partition.opts:
                    try:
                        if os.path.exists(partition.mountpoint):
                            usage = psutil.disk_usage(partition.mountpoint)
                            if usage.total > 0:
                                # Additional size check - USB drives are typically smaller
                                total_gb = usage.total / (1024**3)
                                if total_gb < 2048:  # Less than 2TB
                                    usb_drives.append(partition.mountpoint)
                                    print(f"Found removable drive: {partition.mountpoint} ({total_gb:.1f}GB)")
                    except (PermissionError, OSError):
                        continue
                        
        except Exception as e:
            print(f"Error in fallback USB detection: {e}")
            
        return usb_drives
    
    def check_for_new_drives(self):
        """Check if new USB drives have been inserted"""
        current_drives = set(self.get_usb_drives())
        new_drives = current_drives - self.last_known_drives
        removed_drives = self.last_known_drives - current_drives
        
        self.last_known_drives = current_drives
        
        return list(new_drives), list(removed_drives)
    
    def scan_and_copy_pdf_files(self, source_dir):
        """Fast scan and copy PDF files to temporary folder"""
        found_files = []
        
        try:
            # Ensure destination directory exists
            if not os.path.exists(self.destination_dir):
                os.makedirs(self.destination_dir)
                print(f"Created destination directory: {self.destination_dir}")
        
            print(f"Scanning and copying PDF files from {source_dir} to {self.destination_dir}")
        
            # Scan and copy PDF files
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        try:
                            source_path = os.path.join(root, file)
                        
                            # Verify source file exists
                            if not os.path.exists(source_path):
                                print(f"Source file does not exist: {source_path}")
                                continue
                            
                            file_size = os.path.getsize(source_path)
                        
                            # Create unique filename if duplicate exists
                            dest_filename = file
                            counter = 1
                            while os.path.exists(os.path.join(self.destination_dir, dest_filename)):
                                name, ext = os.path.splitext(file)
                                dest_filename = f"{name}_{counter}{ext}"
                                counter += 1
                        
                            dest_path = os.path.join(self.destination_dir, dest_filename)
                        
                            # Ensure destination directory still exists (in case it was deleted)
                            if not os.path.exists(self.destination_dir):
                                os.makedirs(self.destination_dir)
                        
                            # Copy the file
                            print(f"Copying {source_path} to {dest_path}")
                            shutil.copy2(source_path, dest_path)
                        
                            # Verify the copy was successful
                            if os.path.exists(dest_path):
                                print(f"Successfully copied: {dest_filename}")
                            
                                pages = self.estimate_pdf_pages_fast(file_size)
                            
                                file_info = {
                                    'filename': dest_filename,
                                    'original_path': source_path,
                                    'size': file_size,
                                    'type': '.pdf',
                                    'path': dest_path,  # Use copied path
                                    'pages': pages
                                }
                                found_files.append(file_info)
                            else:
                                print(f"Failed to copy file: {dest_filename}")
                            
                        except Exception as e:
                            print(f"Error copying {file}: {e}")
                            continue
                        
        except Exception as e:
            print(f"Error scanning directory {source_dir}: {e}")
    
        print(f"Successfully copied {len(found_files)} PDF files")
        return found_files
    
    def cleanup_temp_files(self):
        """Delete all files in the temporary directory after printing"""
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
        """Clean up all old temporary folders from previous sessions"""
        try:
            if os.path.exists(self.temp_base_dir):
                print(f"Cleaning up old session folders in {self.temp_base_dir}")
            
                current_session_folder = f"Session_{self.session_id}"
            
                for folder_name in os.listdir(self.temp_base_dir):
                    if folder_name.startswith("Session_") and folder_name != current_session_folder:
                        folder_path = os.path.join(self.temp_base_dir, folder_name)
                        try:
                            if os.path.isdir(folder_path):
                                shutil.rmtree(folder_path)
                                print(f"Deleted old session folder: {folder_name}")
                        except Exception as e:
                            print(f"Error deleting old session folder {folder_name}: {e}")
                        
        except Exception as e:
            print(f"Error cleaning up old session folders: {e}")
    
    def get_temp_folder_info(self):
        """Get information about the current temporary folder"""
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
                    'session_id': self.session_id
                }
            else:
                return None
        except Exception as e:
            print(f"Error getting temp folder info: {e}")
            return None
    
    def estimate_pdf_pages_fast(self, file_size):
        """Fast estimate of PDF pages based on file size"""
        # Rough estimate: 1 page per 50KB for PDF
        estimated_pages = max(1, file_size // 51200)
        return min(estimated_pages, 100)
    
    def estimate_pdf_pages(self, file_path):
        """Estimate number of pages in PDF based on file size"""
        try:
            file_size = os.path.getsize(file_path)
            return self.estimate_pdf_pages_fast(file_size)
        except:
            return 1

    def get_drive_info(self, drive_path):
        """Get detailed information about a drive"""
        try:
            usage = psutil.disk_usage(drive_path)
            total_gb = usage.total / (1024**3)
            free_gb = usage.free / (1024**3)
            used_gb = usage.used / (1024**3)
        
            # Try to get filesystem type
            fs_type = "Unknown"
            partitions = psutil.disk_partitions()
            for partition in partitions:
                if partition.mountpoint == drive_path:
                    fs_type = partition.fstype
                    break
        
            return {
                'path': drive_path,
                'total_gb': total_gb,
                'free_gb': free_gb,
                'used_gb': used_gb,
                'filesystem': fs_type,
                'is_removable': True  # All drives returned by get_usb_drives are removable
            }
        except Exception as e:
            print(f"Error getting drive info for {drive_path}: {e}")
            return None
