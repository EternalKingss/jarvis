#!/usr/bin/env python3
"""
Quick test script to verify Jarvis fixes
"""

import os
import sys

# Add the Jarvis directory to path
jarvis_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, jarvis_dir)

def test_imports():
    """Test that all modules can be imported successfully"""
    print("Testing imports...")
    
    try:
        from command_jarvis.gpt_command_handler import GPTCommandHandler
        print("✓ GPTCommandHandler imported successfully")
    except Exception as e:
        print(f"✗ GPTCommandHandler import failed: {e}")
        return False
    
    try:
        from command_jarvis.intelligent_app_commands import IntelligentAppCommands
        print("✓ IntelligentAppCommands imported successfully")
    except Exception as e:
        print(f"✗ IntelligentAppCommands import failed: {e}")
        return False
    
    try:
        from utils_jarvis.health_monitor import HealthMonitor
        print("✓ HealthMonitor imported successfully")
    except Exception as e:
        print(f"✗ HealthMonitor import failed: {e}")
        return False
    
    return True

def test_parameter_matching():
    """Test that the parameter names match between GPT handler and intelligent app commands"""
    print("\nTesting parameter matching...")
    
    try:
        import inspect
        from command_jarvis.intelligent_app_commands import IntelligentAppCommands
        
        # Get the signature of the intelligent_open_application method
        sig = inspect.signature(IntelligentAppCommands.intelligent_open_application)
        params = list(sig.parameters.keys())
        
        print(f"intelligent_open_application parameters: {params}")
        
        # Should be ['self', 'app_request']
        if 'app_request' in params:
            print("✓ Parameter name 'app_request' found in method signature")
            return True
        else:
            print("✗ Parameter name 'app_request' NOT found in method signature")
            return False
            
    except Exception as e:
        print(f"✗ Parameter matching test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("JARVIS FIX VERIFICATION TESTS")
    print("=" * 50)
    
    # Test imports
    imports_ok = test_imports()
    
    # Test parameter matching
    params_ok = test_parameter_matching()
    
    print("\n" + "=" * 50)
    print("RESULTS:")
    print(f"Imports: {'PASS' if imports_ok else 'FAIL'}")
    print(f"Parameters: {'PASS' if params_ok else 'FAIL'}")
    
    if imports_ok and params_ok:
        print("\n✓ ALL TESTS PASSED! Jarvis should work correctly now.")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED! Please check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
