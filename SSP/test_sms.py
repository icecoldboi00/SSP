#!/usr/bin/env python3
"""
Test script for SMS functionality
Run this script to test the SMS system independently.
"""

import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_sms_initialization():
    """Test SMS system initialization."""
    print("🔍 Testing SMS system initialization...")
    try:
        from sms_manager import get_sms_manager
        sms_manager = get_sms_manager()
        
        if sms_manager.initialize_modem():
            print("✅ SMS system initialized successfully")
            return True
        else:
            print("❌ SMS system initialization failed")
            return False
    except Exception as e:
        print(f"❌ Error testing SMS initialization: {e}")
        return False

def test_sms_sending():
    """Test sending an SMS."""
    print("\n🔍 Testing SMS sending...")
    try:
        from sms_manager import get_sms_manager
        sms_manager = get_sms_manager()
        
        # Send a test message
        test_message = "Test message from SSP system"
        if sms_manager.send_sms(test_message):
            print("✅ Test SMS sent successfully")
            return True
        else:
            print("❌ Test SMS failed to send")
            return False
    except Exception as e:
        print(f"❌ Error testing SMS sending: {e}")
        return False

def test_low_paper_alert():
    """Test low paper alert SMS."""
    print("\n🔍 Testing low paper alert...")
    try:
        from sms_manager import get_sms_manager
        sms_manager = get_sms_manager()
        
        if sms_manager.send_low_paper_alert():
            print("✅ Low paper alert SMS sent successfully")
            return True
        else:
            print("❌ Low paper alert SMS failed to send")
            return False
    except Exception as e:
        print(f"❌ Error testing low paper alert: {e}")
        return False

def main():
    """Run all SMS tests."""
    print("📱 SSP SMS System Test")
    print("=" * 40)
    
    tests = [
        test_sms_initialization,
        test_sms_sending,
        test_low_paper_alert
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 40)
    print("📊 Test Results:")
    
    if all(results):
        print("✅ All SMS tests passed!")
        print("\nSMS system is ready for use.")
    else:
        print("❌ Some SMS tests failed.")
        print("\nPlease check:")
        print("1. GSM module is connected to /dev/serial0")
        print("2. GSM module is powered on")
        print("3. SIM card is inserted and has credit")
        print("4. Phone number is correct in sms_manager.py")

if __name__ == "__main__":
    main()
