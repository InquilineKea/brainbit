#!/usr/bin/env python3
"""
NeuroSDK2 Verification Script

This script verifies that the NeuroSDK2 libraries are correctly installed
and can be imported in Python.
"""

import os
import sys
import site
import platform

def check_python_paths():
    """Check Python's package paths."""
    print("=== Python Package Paths ===")
    for path in sys.path:
        print(f"- {path}")
    
    print("\n=== Site Packages ===")
    for path in site.getsitepackages():
        print(f"- {path}")

def check_library_files():
    """Check for NeuroSDK2 library files."""
    print("\n=== Checking for NeuroSDK2 Library Files ===")
    
    # Check home directory
    home_dir = os.path.expanduser("~")
    home_lib = os.path.join(home_dir, "Library", "neurosdk2", "libneurosdk2.dylib")
    print(f"Home library: {home_lib} - {'Exists' if os.path.exists(home_lib) else 'Not found'}")
    
    # Check site-packages
    for site_dir in site.getsitepackages():
        lib_path = os.path.join(site_dir, "neurosdk2_lib", "libneurosdk2.dylib")
        print(f"Site library: {lib_path} - {'Exists' if os.path.exists(lib_path) else 'Not found'}")
    
    # Check system directory
    system_lib = "/usr/local/lib/libneurosdk2.dylib"
    print(f"System library: {system_lib} - {'Exists' if os.path.exists(system_lib) else 'Not found'}")

def check_pyneurosdk2():
    """Check if pyneurosdk2 can be imported."""
    print("\n=== Checking pyneurosdk2 Import ===")
    try:
        import pyneurosdk2
        print("Successfully imported pyneurosdk2")
        print(f"Package location: {pyneurosdk2.__file__}")
        print(f"Package version: {getattr(pyneurosdk2, '__version__', 'Unknown')}")
    except ImportError as e:
        print(f"Error importing pyneurosdk2: {e}")
    
    try:
        from pyneurosdk2 import managers
        print("Successfully imported pyneurosdk2.managers")
    except ImportError as e:
        print(f"Error importing pyneurosdk2.managers: {e}")

def check_device_import():
    """Check if pyneurosdk2 device module can be imported."""
    print("\n=== Checking pyneurosdk2 Device Module ===")
    try:
        from pyneurosdk2.device import Device, DeviceInfo
        from pyneurosdk2.enums import DeviceState, DeviceType
        from pyneurosdk2.managers import DeviceScanner
        print("Successfully imported all required pyneurosdk2 components")
    except ImportError as e:
        print(f"Error importing pyneurosdk2 components: {e}")
    except Exception as e:
        print(f"Error: {e}")

def attempt_device_scan():
    """Attempt to scan for devices."""
    print("\n=== Attempting Device Scan ===")
    try:
        from pyneurosdk2.managers import DeviceScanner
        
        scanner = DeviceScanner()
        scanner.start_scan()
        print("Device scanner created and started successfully")
        
        import time
        time.sleep(3)  # Scan for 3 seconds
        
        devices = scanner.list_devices()
        print(f"Found {len(devices)} devices")
        
        scanner.stop_scan()
        print("Scanner stopped successfully")
        
    except Exception as e:
        print(f"Error during device scan: {e}")

def main():
    """Main function."""
    print(f"=== NeuroSDK2 Verification ===")
    print(f"Python version: {sys.version}")
    print(f"Platform: {platform.platform()}")
    
    check_python_paths()
    check_library_files()
    check_pyneurosdk2()
    check_device_import()
    attempt_device_scan()
    
    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    main()
