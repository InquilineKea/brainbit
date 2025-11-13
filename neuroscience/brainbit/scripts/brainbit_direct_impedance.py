#!/usr/bin/env python3
"""
BrainBit Direct Impedance Reader

This script attempts to read impedance values directly from BrainBit 
using raw data access methods.
"""

import time
import numpy as np
import ctypes
import os
import platform
from ctypes import c_int, c_double, c_char_p, c_float, byref, CDLL

# Check system architecture for loading appropriate library
system = platform.system()
is_64bits = platform.architecture()[0] == '64bit'

# Get the location of the brainflow package so we can access the libs directly
import brainflow
brainflow_dir = os.path.dirname(brainflow.__file__)
print(f"BrainFlow directory: {brainflow_dir}")

# Load the neurosdk library directly
if system == 'Windows':
    if is_64bits:
        lib_path = os.path.join(brainflow_dir, 'lib', 'neurosdk-x64.dll')
    else:
        lib_path = os.path.join(brainflow_dir, 'lib', 'neurosdk-x86.dll')
elif system == 'Darwin':  # macOS
    lib_path = os.path.join(brainflow_dir, 'lib', 'libneurosdk-shared.dylib')
else:  # Linux
    lib_path = os.path.join(brainflow_dir, 'lib', 'libneurosdk-shared.so')

print(f"Loading library from: {lib_path}")
try:
    neurosdk = ctypes.CDLL(lib_path)
    print("NeuroSDK library loaded successfully")
except Exception as e:
    print(f"Failed to load NeuroSDK library: {e}")
    exit(1)

# Define SDK functions we need
try:
    # Define error callback
    ErrorCallback = ctypes.CFUNCTYPE(None, c_int, c_char_p)
    
    # Device discovery functions
    neurosdk.create_scanner_info.restype = ctypes.c_void_p
    neurosdk.create_scanner.argtypes = [ctypes.c_void_p, ErrorCallback]
    neurosdk.create_scanner.restype = ctypes.c_void_p
    neurosdk.scan.argtypes = [ctypes.c_void_p, ctypes.c_int]
    neurosdk.scan.restype = None
    neurosdk.get_device_list.argtypes = [ctypes.c_void_p]
    neurosdk.get_device_list.restype = ctypes.c_void_p
    neurosdk.get_device_list_size.argtypes = [ctypes.c_void_p]
    neurosdk.get_device_list_size.restype = ctypes.c_int
    neurosdk.get_device_from_list.argtypes = [ctypes.c_void_p, ctypes.c_int]
    neurosdk.get_device_from_list.restype = ctypes.c_void_p
    neurosdk.free_device_info.argtypes = [ctypes.c_void_p]
    neurosdk.free_device_info.restype = None
    
    # Device functions
    neurosdk.create_device.argtypes = [ctypes.c_void_p, ErrorCallback]
    neurosdk.create_device.restype = ctypes.c_void_p
    neurosdk.free_device.argtypes = [ctypes.c_void_p]
    neurosdk.free_device.restype = None
    neurosdk.free_scanner.argtypes = [ctypes.c_void_p]
    neurosdk.free_scanner.restype = None
    neurosdk.free_scanner_info.argtypes = [ctypes.c_void_p]
    neurosdk.free_scanner_info.restype = None
    
    # Connect/disconnect functions
    neurosdk.connect.argtypes = [ctypes.c_void_p]
    neurosdk.connect.restype = None
    neurosdk.disconnect.argtypes = [ctypes.c_void_p]
    neurosdk.disconnect.restype = None
    
    # BrainBit specific functions
    neurosdk.is_brainbit.argtypes = [ctypes.c_void_p]
    neurosdk.is_brainbit.restype = ctypes.c_bool
    neurosdk.brainbit_set_resistance_meas.argtypes = [ctypes.c_void_p, ctypes.c_bool]
    neurosdk.brainbit_set_resistance_meas.restype = None
    neurosdk.brainbit_resistance_meas_enabled.argtypes = [ctypes.c_void_p]
    neurosdk.brainbit_resistance_meas_enabled.restype = ctypes.c_bool
    
    # Get data functions
    neurosdk.get_data_labels.argtypes = [ctypes.c_void_p]
    neurosdk.get_data_labels.restype = ctypes.POINTER(ctypes.c_char_p)
    neurosdk.get_data_labels_count.argtypes = [ctypes.c_void_p]
    neurosdk.get_data_labels_count.restype = ctypes.c_int
    
    # Signal functions
    neurosdk.add_resistance_data_received_callback.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    neurosdk.add_resistance_data_received_callback.restype = None
    
    print("NeuroSDK functions defined successfully")
except Exception as e:
    print(f"Failed to define SDK functions: {e}")
    exit(1)
    
# Callback for error handling
@ErrorCallback
def error_callback(error_code, error_message):
    print(f"Error {error_code}: {error_message.decode('utf-8')}")

# Callback type for resistance data
ResistanceDataCallback = ctypes.CFUNCTYPE(
    None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_double), ctypes.c_int
)

# Global variable to store resistance data
resistance_data = {}

# Callback function for resistance data
@ResistanceDataCallback
def resistance_data_callback(device_ptr, data_ptr, data_count):
    if data_count > 0:
        # Convert data to Python list
        data_array = [data_ptr[i] for i in range(data_count)]
        
        # Map to electrodes (assuming 4 channels: T3, T4, O1, O2)
        electrodes = ['T3', 'T4', 'O1', 'O2']
        for i, value in enumerate(data_array[:min(len(electrodes), data_count)]):
            resistance_data[electrodes[i]] = value
        
        print(f"Received resistance data: {resistance_data}")

def main():
    try:
        print("Starting BrainBit impedance measurement...")
        
        # Create scanner info
        scanner_info = neurosdk.create_scanner_info()
        if not scanner_info:
            print("Failed to create scanner info")
            return
        print("Scanner info created")
        
        # Create scanner
        scanner = neurosdk.create_scanner(scanner_info, error_callback)
        if not scanner:
            print("Failed to create scanner")
            neurosdk.free_scanner_info(scanner_info)
            return
        print("Scanner created")
        
        # Scan for devices (timeout 5 seconds)
        print("Scanning for devices (5 seconds)...")
        neurosdk.scan(scanner, 5)
        
        # Get device list
        device_list = neurosdk.get_device_list(scanner)
        if not device_list:
            print("No devices found")
            neurosdk.free_scanner(scanner)
            neurosdk.free_scanner_info(scanner_info)
            return
        
        # Get number of devices
        device_count = neurosdk.get_device_list_size(device_list)
        print(f"Found {device_count} devices")
        
        if device_count == 0:
            print("No devices found")
            neurosdk.free_device_info(device_list)
            neurosdk.free_scanner(scanner)
            neurosdk.free_scanner_info(scanner_info)
            return
        
        # Get first device
        device_info = neurosdk.get_device_from_list(device_list, 0)
        if not device_info:
            print("Failed to get device info")
            neurosdk.free_device_info(device_list)
            neurosdk.free_scanner(scanner)
            neurosdk.free_scanner_info(scanner_info)
            return
        print("Got device info")
        
        # Create device
        device = neurosdk.create_device(device_info, error_callback)
        if not device:
            print("Failed to create device")
            neurosdk.free_device_info(device_info)
            neurosdk.free_device_info(device_list)
            neurosdk.free_scanner(scanner)
            neurosdk.free_scanner_info(scanner_info)
            return
        print("Device created")
        
        # Check if device is BrainBit
        is_brainbit = neurosdk.is_brainbit(device)
        if not is_brainbit:
            print("Device is not a BrainBit")
            neurosdk.free_device(device)
            neurosdk.free_device_info(device_info)
            neurosdk.free_device_info(device_list)
            neurosdk.free_scanner(scanner)
            neurosdk.free_scanner_info(scanner_info)
            return
        print("Device is a BrainBit")
        
        # Connect to device
        print("Connecting to device...")
        neurosdk.connect(device)
        print("Connected to device")
        
        # Register callback for resistance data
        resistance_callback = ResistanceDataCallback(resistance_data_callback)
        neurosdk.add_resistance_data_received_callback(device, resistance_callback)
        print("Resistance data callback registered")
        
        # Enable resistance measurement
        print("Enabling resistance measurement...")
        neurosdk.brainbit_set_resistance_meas(device, True)
        
        # Check if resistance measurement is enabled
        resistance_enabled = neurosdk.brainbit_resistance_meas_enabled(device)
        print(f"Resistance measurement enabled: {resistance_enabled}")
        
        # Wait for 10 seconds to collect data
        print("Collecting resistance data for 10 seconds...")
        for i in range(10):
            time.sleep(1)
            print(f"Time elapsed: {i+1}s, Current values: {resistance_data}")
        
        # Disable resistance measurement
        print("Disabling resistance measurement...")
        neurosdk.brainbit_set_resistance_meas(device, False)
        
        # Disconnect from device
        print("Disconnecting from device...")
        neurosdk.disconnect(device)
        print("Disconnected from device")
        
        # Clean up resources
        neurosdk.free_device(device)
        neurosdk.free_device_info(device_info)
        neurosdk.free_device_info(device_list)
        neurosdk.free_scanner(scanner)
        neurosdk.free_scanner_info(scanner_info)
        print("Resources cleaned up")
        
        # Print final results
        print("\nFinal impedance values:")
        for electrode, value in resistance_data.items():
            print(f"{electrode}: {value:.1f} kOhm")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
