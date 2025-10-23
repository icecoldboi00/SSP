#!/usr/bin/env python3
"""
Printing System Diagnostic Script

This script helps diagnose printing issues by checking:
1. Required libraries (PyMuPDF)
2. CUPS installation and status
3. Printer availability
4. File system permissions
5. PDF file accessibility

Run this script to identify the root cause of printing problems.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def check_python_version():
    """Check Python version compatibility."""
    print("🐍 Python Version Check")
    print(f"   Python version: {sys.version}")
    if sys.version_info < (3, 6):
        print("   ❌ Python 3.6+ required")
        return False
    print("   ✅ Python version OK")
    return True

def check_pymupdf():
    """Check if PyMuPDF is installed and working."""
    print("\n📚 PyMuPDF Library Check")
    try:
        import fitz
        print("   ✅ PyMuPDF imported successfully")
        
        # Test basic functionality
        test_doc = fitz.open()
        test_doc.new_page()
        test_doc.close()
        print("   ✅ PyMuPDF basic functionality works")
        return True
    except ImportError:
        print("   ❌ PyMuPDF not installed")
        print("   💡 Install with: pip install PyMuPDF")
        return False
    except Exception as e:
        print(f"   ❌ PyMuPDF error: {e}")
        return False

def check_cups():
    """Check CUPS installation and status."""
    print("\n🖨️ CUPS System Check")
    
    # Check if lp command exists
    try:
        result = subprocess.run(['which', 'lp'], capture_output=True, text=True)
        if result.returncode != 0:
            print("   ❌ CUPS 'lp' command not found")
            print("   💡 Install CUPS: sudo apt-get install cups")
            return False
        print("   ✅ CUPS 'lp' command found")
    except Exception as e:
        print(f"   ❌ Error checking lp command: {e}")
        return False
    
    # Check if CUPS daemon is running
    try:
        result = subprocess.run(['pgrep', 'cupsd'], capture_output=True, text=True)
        if result.returncode != 0:
            print("   ❌ CUPS daemon not running")
            print("   💡 Start CUPS: sudo systemctl start cups")
            return False
        print("   ✅ CUPS daemon is running")
    except Exception as e:
        print(f"   ❌ Error checking CUPS daemon: {e}")
        return False
    
    return True

def check_printers():
    """Check available printers."""
    print("\n🖨️ Printer Check")
    
    try:
        # List all printers
        result = subprocess.run(['lpstat', '-p'], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print("   ❌ Could not list printers")
            print(f"   Error: {result.stderr}")
            return False
        
        printers = []
        for line in result.stdout.split('\n'):
            if line.strip() and 'printer' in line.lower():
                printers.append(line.strip())
        
        if not printers:
            print("   ❌ No printers found")
            print("   💡 Add a printer: sudo lpadmin -p <name> -E -v <device> -m <driver>")
            return False
        
        print(f"   ✅ Found {len(printers)} printer(s):")
        for printer in printers:
            print(f"      {printer}")
        
        return True
        
    except subprocess.TimeoutExpired:
        print("   ❌ Printer list command timed out")
        return False
    except Exception as e:
        print(f"   ❌ Error listing printers: {e}")
        return False

def check_specific_printer(printer_name):
    """Check specific printer status."""
    print(f"\n🔍 Checking Printer: {printer_name}")
    
    try:
        result = subprocess.run(['lpstat', '-p', printer_name], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print(f"   ❌ Printer '{printer_name}' not found")
            return False
        
        output = result.stdout.lower()
        print(f"   Status: {result.stdout.strip()}")
        
        if 'offline' in output or 'stopped' in output:
            print("   ❌ Printer is offline or stopped")
            return False
        elif 'jam' in output:
            print("   ❌ Paper jam detected")
            return False
        elif 'error' in output:
            print("   ❌ Printer error detected")
            return False
        else:
            print("   ✅ Printer is ready")
            return True
            
    except subprocess.TimeoutExpired:
        print("   ❌ Printer check timed out")
        return False
    except Exception as e:
        print(f"   ❌ Error checking printer: {e}")
        return False

def check_file_system():
    """Check file system permissions and temp directory."""
    print("\n📁 File System Check")
    
    # Check temp directory
    try:
        temp_dir = tempfile.gettempdir()
        print(f"   Temp directory: {temp_dir}")
        
        # Test write permission
        test_file = os.path.join(temp_dir, "print_test.tmp")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print("   ✅ Temp directory writable")
        
    except Exception as e:
        print(f"   ❌ Temp directory error: {e}")
        return False
    
    # Check current directory permissions
    try:
        current_dir = os.getcwd()
        print(f"   Current directory: {current_dir}")
        
        # Test write permission
        test_file = os.path.join(current_dir, "print_test.tmp")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print("   ✅ Current directory writable")
        
    except Exception as e:
        print(f"   ❌ Current directory error: {e}")
        return False
    
    return True

def check_pdf_file(file_path):
    """Check if a PDF file is accessible and valid."""
    print(f"\n📄 PDF File Check: {file_path}")
    
    if not os.path.exists(file_path):
        print("   ❌ File does not exist")
        return False
    
    if not os.path.isfile(file_path):
        print("   ❌ Path is not a file")
        return False
    
    file_size = os.path.getsize(file_path)
    print(f"   File size: {file_size} bytes")
    
    if file_size == 0:
        print("   ❌ File is empty")
        return False
    
    # Try to open with PyMuPDF
    try:
        import fitz
        doc = fitz.open(file_path)
        page_count = len(doc)
        print(f"   ✅ PDF opened successfully, {page_count} pages")
        doc.close()
        return True
    except Exception as e:
        print(f"   ❌ PDF file error: {e}")
        return False

def test_print_command(printer_name):
    """Test basic print command."""
    print(f"\n🧪 Print Command Test")
    
    try:
        # Create a simple test file
        test_content = "Print Test\nThis is a test document."
        test_file = os.path.join(tempfile.gettempdir(), "print_test.txt")
        
        with open(test_file, 'w') as f:
            f.write(test_content)
        
        # Try to print
        cmd = ['lp', '-d', printer_name, test_file]
        print(f"   Command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        # Clean up test file
        os.remove(test_file)
        
        if result.returncode == 0:
            print("   ✅ Print command successful")
            print(f"   Output: {result.stdout}")
            return True
        else:
            print("   ❌ Print command failed")
            print(f"   Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("   ❌ Print command timed out")
        return False
    except Exception as e:
        print(f"   ❌ Print command error: {e}")
        return False

def main():
    """Run all diagnostic checks."""
    print("🔧 Printing System Diagnostic Tool")
    print("=" * 50)
    
    all_good = True
    
    # Basic checks
    all_good &= check_python_version()
    all_good &= check_pymupdf()
    all_good &= check_cups()
    all_good &= check_file_system()
    
    # Printer checks
    if check_printers():
        # Try to find the configured printer
        printer_name = "HP_Smart_Tank_580_590_series_5E0E1D_USB"  # Default from code
        all_good &= check_specific_printer(printer_name)
        
        # Test print command
        all_good &= test_print_command(printer_name)
    else:
        all_good = False
    
    # Summary
    print("\n" + "=" * 50)
    if all_good:
        print("✅ All checks passed! Printing should work.")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        print("\n💡 Common solutions:")
        print("   1. Install PyMuPDF: pip install PyMuPDF")
        print("   2. Install CUPS: sudo apt-get install cups")
        print("   3. Start CUPS: sudo systemctl start cups")
        print("   4. Add printer: sudo lpadmin -p <name> -E -v <device> -m <driver>")
        print("   5. Check printer name in config.py")

if __name__ == "__main__":
    main()
