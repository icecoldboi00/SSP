#!/usr/bin/env python3
"""
Test script for printer functionality on Raspberry Pi
Run this script to verify your printer setup before running the main application.
"""

import os
import sys
import subprocess
import tempfile

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_cups_installation():
    """Test if CUPS is installed and working."""
    print("🔍 Testing CUPS installation...")
    try:
        result = subprocess.run(['which', 'lp'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ CUPS 'lp' command found")
            return True
        else:
            print("❌ CUPS 'lp' command not found")
            print("   Install CUPS with: sudo apt install cups cups-client")
            return False
    except Exception as e:
        print(f"❌ Error checking CUPS: {e}")
        return False

def test_printer_availability():
    """Test if the configured printer is available."""
    print("\n🔍 Testing printer availability...")
    
    # Import the printer manager to get the configured printer name
    try:
        from printing.printer_manager import PRINTER_NAME
        printer_name = PRINTER_NAME
        print(f"Configured printer: {printer_name}")
    except ImportError:
        print("❌ Could not import printer manager")
        return False
    
    try:
        # Check if printer exists
        result = subprocess.run(['lpstat', '-p', printer_name], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Printer '{printer_name}' is available")
            return True
        else:
            print(f"❌ Printer '{printer_name}' not found")
            print("Available printers:")
            subprocess.run(['lpstat', '-p'], capture_output=False)
            return False
    except Exception as e:
        print(f"❌ Error checking printer: {e}")
        return False

def test_pymupdf():
    """Test if PyMuPDF is installed."""
    print("\n🔍 Testing PyMuPDF installation...")
    try:
        import fitz
        print("✅ PyMuPDF is installed")
        return True
    except ImportError:
        print("❌ PyMuPDF not installed")
        print("   Install with: pip3 install PyMuPDF")
        return False

def test_print_job():
    """Test a simple print job."""
    print("\n🔍 Testing print job...")
    
    try:
        from printing.printer_manager import PRINTER_NAME
        
        # Create a simple test file
        test_content = "Test print from SSP system\n\nThis is a test to verify printer functionality."
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(test_content)
            test_file = f.name
        
        # Try to print the test file using the exact command format
        result = subprocess.run([
            'lp', '-d', 'HP_Smart_Tank_580_590_series_5E0E1D_USB', 
            '-o', 'print-color-mode=monochrome', test_file
        ], capture_output=True, text=True)
        
        # Clean up test file
        os.unlink(test_file)
        
        if result.returncode == 0:
            print("✅ Test print job sent successfully")
            print(f"   Job ID: {result.stdout.strip()}")
            return True
        else:
            print("❌ Test print job failed")
            print(f"   Error: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing print job: {e}")
        return False

def main():
    """Run all tests."""
    print("🖨️  SSP Printer Setup Test")
    print("=" * 40)
    
    tests = [
        test_cups_installation,
        test_pymupdf,
        test_printer_availability,
        test_print_job
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 40)
    print("📊 Test Results:")
    
    if all(results):
        print("✅ All tests passed! Your printer setup is ready.")
        print("\nYou can now run the main application with:")
        print("   python3 main_app.py")
    else:
        print("❌ Some tests failed. Please fix the issues above.")
        print("\nRefer to RASPBERRY_PI_SETUP.md for detailed setup instructions.")

if __name__ == "__main__":
    main()
