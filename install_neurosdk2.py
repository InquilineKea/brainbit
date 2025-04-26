#!/usr/bin/env python3
"""
NeuroSDK2 Installer for macOS

This script installs the NeuroSDK2 libraries required for BrainBit devices on macOS.
It handles both the Python package and the native libraries.
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
import tempfile

def run_command(command):
    """Run a shell command and print the output."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}")
    return result.returncode == 0

def install_pyneurosdk2():
    """Install the Python NeuroSDK2 package using pip."""
    print("\n=== Installing Python NeuroSDK2 package ===")
    return run_command("pip install pyneurosdk2 --upgrade")

def download_native_libraries():
    """Download the native NeuroSDK2 libraries from GitHub."""
    print("\n=== Downloading native NeuroSDK2 libraries ===")
    temp_dir = tempfile.mkdtemp()
    os.chdir(temp_dir)
    
    # Clone the repository
    success = run_command("git clone --depth 1 https://github.com/BrainbitLLC/apple_neurosdk2.git")
    if not success:
        print("Failed to clone repository")
        return None
    
    return os.path.join(temp_dir, "apple_neurosdk2")

def install_macos_libraries(repo_path):
    """Install the macOS-specific libraries."""
    print("\n=== Installing macOS libraries ===")
    
    # Source paths
    lib_source = os.path.join(repo_path, "macos", "libneurosdk2.dylib")
    headers_source = os.path.join(repo_path, "macos", "Headers")
    
    # Destination paths
    home_dir = str(Path.home())
    lib_dest = os.path.join(home_dir, "Library", "neurosdk2")
    headers_dest = os.path.join(lib_dest, "include")
    
    # Create destination directories
    os.makedirs(lib_dest, exist_ok=True)
    os.makedirs(headers_dest, exist_ok=True)
    
    # Copy library
    print(f"Copying library to {lib_dest}")
    shutil.copy2(lib_source, lib_dest)
    
    # Copy headers
    print(f"Copying headers to {headers_dest}")
    for header_file in os.listdir(headers_source):
        shutil.copy2(os.path.join(headers_source, header_file), headers_dest)
    
    # Create a symbolic link
    symlink_path = "/usr/local/lib/libneurosdk2.dylib"
    if os.path.exists(symlink_path):
        print(f"Removing existing symlink: {symlink_path}")
        try:
            os.remove(symlink_path)
        except PermissionError:
            print(f"Warning: Could not remove existing symlink. You might need to run: sudo rm {symlink_path}")
    
    try:
        print(f"Creating symbolic link: {symlink_path} -> {os.path.join(lib_dest, 'libneurosdk2.dylib')}")
        os.symlink(os.path.join(lib_dest, "libneurosdk2.dylib"), symlink_path)
    except (PermissionError, FileNotFoundError):
        print(f"Warning: Could not create symlink. You might need to run:")
        print(f"sudo ln -s {os.path.join(lib_dest, 'libneurosdk2.dylib')} {symlink_path}")
    
    return True

def create_test_script():
    """Create a test script to verify the installation."""
    print("\n=== Creating test script ===")
    
    test_script_path = "test_neurosdk2.py"
    test_script_content = """#!/usr/bin/env python3
\"\"\"
NeuroSDK2 Test Script

This script verifies that the NeuroSDK2 installation is working correctly.
\"\"\"

import time
import os
from pyneurosdk2.device import Device, DeviceInfo, ParameterName
from pyneurosdk2.enums import DeviceState, DeviceType, SamplingFrequency
from pyneurosdk2.managers import MemoryManager, DeviceScanner

def print_device_info(info):
    \"\"\"Print device information.\"\"\"
    print(f"Name: {info.name}")
    print(f"Address: {info.address}")
    print(f"Serial Number: {info.serial_number}")
    print(f"Type: {info.device_type}")

def main():
    # Create a scanner
    print("Creating device scanner...")
    scanner = DeviceScanner()
    scanner.start_scan()
    
    print("\\nLooking for BrainBit devices...")
    print("Scanning for 10 seconds...")
    
    # Scan for devices
    start_time = time.time()
    while time.time() - start_time < 10:
        # Get found devices
        devices_list = scanner.list_devices()
        
        # Filter BrainBit devices
        brainbit_devices = [
            info for info in devices_list 
            if info.device_type in [
                DeviceType.BrainBit.value, 
                DeviceType.BrainBitBlack.value,
                DeviceType.BrainBitBlackBtLE.value,
                DeviceType.BrainBitFlex.value
            ]
        ]
        
        if brainbit_devices:
            print(f"Found {len(brainbit_devices)} BrainBit device(s):")
            for i, info in enumerate(brainbit_devices):
                print(f"\\nDevice {i+1}:")
                print_device_info(info)
            break
        
        time.sleep(1)
    else:
        print("No BrainBit devices found in 10 seconds.")
    
    # Clean up
    scanner.stop_scan()
    print("\\nTest completed successfully!")
    print("NeuroSDK2 is installed correctly.")

if __name__ == "__main__":
    main()
"""
    
    with open(test_script_path, "w") as f:
        f.write(test_script_content)
    
    print(f"Test script created: {test_script_path}")
    return test_script_path

def main():
    """Main installation function."""
    print("=== NeuroSDK2 Installer for macOS ===")
    
    # Check if we're on macOS
    if platform.system() != "Darwin":
        print("This installer only works on macOS.")
        return
    
    # Install Python package
    if not install_pyneurosdk2():
        print("Failed to install Python package")
        return
    
    # Download native libraries
    repo_path = download_native_libraries()
    if not repo_path:
        print("Failed to download native libraries")
        return
    
    # Install macOS libraries
    if not install_macos_libraries(repo_path):
        print("Failed to install macOS libraries")
        return
    
    # Create test script
    test_script = create_test_script()
    
    print("\n=== Installation complete! ===")
    print("The NeuroSDK2 libraries have been installed.")
    print(f"Run the test script to verify the installation: python {test_script}")
    print("\nNote: If any symbolic link warnings appeared, you may need to run the")
    print("suggested sudo commands to complete the installation.")

if __name__ == "__main__":
    main()
