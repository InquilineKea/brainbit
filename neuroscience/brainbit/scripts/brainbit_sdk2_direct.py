#!/usr/bin/env python3
"""
BrainBit SDK2 Direct Implementation

This script bypasses the standard Python import mechanism and directly uses
the NeuroSDK2 native library via ctypes for BrainBit devices.

This approach should work even if the standard Python package import fails.
"""

import os
import sys
import time
import ctypes
import threading
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from pathlib import Path
from enum import Enum

# Dynamic library loading
def load_neurosdk2():
    """Load the NeuroSDK2 library directly using ctypes."""
    # Try different paths for the library
    paths_to_try = [
        # User's home directory
        os.path.join(str(Path.home()), "Library", "neurosdk2", "libneurosdk2.dylib"),
        # Site-packages
        os.path.join(sys.prefix, "lib", "python3.11", "site-packages", "neurosdk2_lib", "libneurosdk2.dylib"),
        # System library
        "/usr/local/lib/libneurosdk2.dylib"
    ]
    
    for path in paths_to_try:
        if os.path.exists(path):
            try:
                return ctypes.CDLL(path)
            except Exception as e:
                print(f"Error loading library from {path}: {e}")
    
    raise ImportError("Failed to load NeuroSDK2 library from any location")

# Load the library
try:
    neurosdk2_lib = load_neurosdk2()
    print("Successfully loaded NeuroSDK2 native library")
except ImportError as e:
    print(f"Error: {e}")
    sys.exit(1)

# Define enums and constants
class DeviceType(Enum):
    BrainBit = 1
    BrainBitBlack = 6 
    BrainBitBlackBtLE = 7
    BrainBitFlex = 10

class SamplingFrequency(Enum):
    Hz125 = 0
    Hz250 = 1
    Hz500 = 2
    Hz1000 = 3

class SignalType(Enum):
    SignalEeg = 0
    SignalResistance = 1

class ChannelType(Enum):
    T3 = 0
    T4 = 1
    O1 = 2
    O2 = 3

# Define C function prototypes
neurosdk2_lib.bbDeviceCreate.argtypes = [ctypes.c_char_p, ctypes.c_int]
neurosdk2_lib.bbDeviceCreate.restype = ctypes.c_void_p

neurosdk2_lib.bbDeviceConnect.argtypes = [ctypes.c_void_p]
neurosdk2_lib.bbDeviceConnect.restype = ctypes.c_int

neurosdk2_lib.bbDeviceDisconnect.argtypes = [ctypes.c_void_p]
neurosdk2_lib.bbDeviceDisconnect.restype = ctypes.c_int

neurosdk2_lib.bbDeviceStartSignal.argtypes = [ctypes.c_void_p, ctypes.c_int]
neurosdk2_lib.bbDeviceStartSignal.restype = ctypes.c_int

neurosdk2_lib.bbDeviceStopSignal.argtypes = [ctypes.c_void_p, ctypes.c_int]
neurosdk2_lib.bbDeviceStopSignal.restype = ctypes.c_int

neurosdk2_lib.bbDeviceIsSignalEnabled.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_bool)]
neurosdk2_lib.bbDeviceIsSignalEnabled.restype = ctypes.c_int

neurosdk2_lib.bbDeviceReadBatteryPower.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
neurosdk2_lib.bbDeviceReadBatteryPower.restype = ctypes.c_int

neurosdk2_lib.bbCreateScanner.restype = ctypes.c_void_p

neurosdk2_lib.bbScannerStart.argtypes = [ctypes.c_void_p]
neurosdk2_lib.bbScannerStart.restype = ctypes.c_int

neurosdk2_lib.bbScannerStop.argtypes = [ctypes.c_void_p]
neurosdk2_lib.bbScannerStop.restype = ctypes.c_int

neurosdk2_lib.bbScannerGetDevicesCount.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
neurosdk2_lib.bbScannerGetDevicesCount.restype = ctypes.c_int

neurosdk2_lib.bbScannerGetDeviceName.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
neurosdk2_lib.bbScannerGetDeviceName.restype = ctypes.c_int

neurosdk2_lib.bbScannerGetDeviceAddress.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
neurosdk2_lib.bbScannerGetDeviceAddress.restype = ctypes.c_int

neurosdk2_lib.bbScannerGetDeviceType.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
neurosdk2_lib.bbScannerGetDeviceType.restype = ctypes.c_int

# Define callback type for signal reception
SIGNAL_CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_int, 
                                  ctypes.POINTER(ctypes.c_double), ctypes.c_int)

neurosdk2_lib.bbDeviceAddSignalCallback.argtypes = [ctypes.c_void_p, SIGNAL_CALLBACK, ctypes.c_void_p]
neurosdk2_lib.bbDeviceAddSignalCallback.restype = ctypes.c_int

# Global variables for EEG data
buffer_size = 1250  # 5 seconds at 250 Hz
eeg_data = {
    "T3": np.zeros(buffer_size),
    "T4": np.zeros(buffer_size),
    "O1": np.zeros(buffer_size),
    "O2": np.zeros(buffer_size)
}
eeg_lock = threading.Lock()

# Callback for EEG signal processing
@SIGNAL_CALLBACK
def signal_callback(device_ptr, signal_type, signal_ptr, signal_length):
    """Callback function for signal data reception."""
    if signal_type == SignalType.SignalEeg.value:
        # Convert C array to Python list
        signal_array = [signal_ptr[i] for i in range(signal_length)]
        
        # The order of channels in the signal array should be: T3, T4, O1, O2
        # Each sample will have 4 values
        if signal_length >= 4:
            with eeg_lock:
                # Update the data buffers (roll and append new data)
                eeg_data["T3"] = np.roll(eeg_data["T3"], -1)
                eeg_data["T3"][-1] = signal_array[0]
                
                eeg_data["T4"] = np.roll(eeg_data["T4"], -1)
                eeg_data["T4"][-1] = signal_array[1]
                
                eeg_data["O1"] = np.roll(eeg_data["O1"], -1)
                eeg_data["O1"][-1] = signal_array[2]
                
                eeg_data["O2"] = np.roll(eeg_data["O2"], -1)
                eeg_data["O2"][-1] = signal_array[3]

class DeviceScanner:
    """Class to scan for BrainBit devices."""
    def __init__(self):
        self.scanner_ptr = neurosdk2_lib.bbCreateScanner()
        if not self.scanner_ptr:
            raise RuntimeError("Failed to create device scanner")
    
    def start_scan(self):
        """Start scanning for devices."""
        result = neurosdk2_lib.bbScannerStart(self.scanner_ptr)
        if result != 0:
            raise RuntimeError(f"Failed to start scanner, error code: {result}")
    
    def stop_scan(self):
        """Stop scanning for devices."""
        result = neurosdk2_lib.bbScannerStop(self.scanner_ptr)
        if result != 0:
            raise RuntimeError(f"Failed to stop scanner, error code: {result}")
    
    def list_devices(self):
        """List all found devices."""
        count = ctypes.c_int()
        result = neurosdk2_lib.bbScannerGetDevicesCount(self.scanner_ptr, ctypes.byref(count))
        if result != 0:
            raise RuntimeError(f"Failed to get device count, error code: {result}")
        
        devices = []
        for i in range(count.value):
            # Get device name
            name_buffer = ctypes.create_string_buffer(128)
            result = neurosdk2_lib.bbScannerGetDeviceName(self.scanner_ptr, i, name_buffer, 128)
            if result != 0:
                continue
            
            # Get device address
            addr_buffer = ctypes.create_string_buffer(128)
            result = neurosdk2_lib.bbScannerGetDeviceAddress(self.scanner_ptr, i, addr_buffer, 128)
            if result != 0:
                continue
            
            # Get device type
            device_type = ctypes.c_int()
            result = neurosdk2_lib.bbScannerGetDeviceType(self.scanner_ptr, i, ctypes.byref(device_type))
            if result != 0:
                continue
            
            # Add device to the list
            devices.append({
                'name': name_buffer.value.decode('utf-8'),
                'address': addr_buffer.value.decode('utf-8'),
                'type': device_type.value
            })
        
        return devices

class BrainBitDevice:
    """Class to interact with a BrainBit device."""
    def __init__(self, address, device_type):
        self.address = address
        self.device_type = device_type
        self.device_ptr = neurosdk2_lib.bbDeviceCreate(address.encode('utf-8'), device_type)
        if not self.device_ptr:
            raise RuntimeError(f"Failed to create device from address: {address}")
        
        # Register signal callback
        self.callback_ref = signal_callback  # Keep a reference
        result = neurosdk2_lib.bbDeviceAddSignalCallback(self.device_ptr, self.callback_ref, None)
        if result != 0:
            raise RuntimeError(f"Failed to register signal callback, error code: {result}")
    
    def connect(self):
        """Connect to the device."""
        result = neurosdk2_lib.bbDeviceConnect(self.device_ptr)
        if result != 0:
            raise RuntimeError(f"Failed to connect to device, error code: {result}")
    
    def disconnect(self):
        """Disconnect from the device."""
        result = neurosdk2_lib.bbDeviceDisconnect(self.device_ptr)
        if result != 0:
            raise RuntimeError(f"Failed to disconnect from device, error code: {result}")
    
    def start_signal(self, signal_type=SignalType.SignalEeg):
        """Start signal acquisition."""
        result = neurosdk2_lib.bbDeviceStartSignal(self.device_ptr, signal_type.value)
        if result != 0:
            raise RuntimeError(f"Failed to start signal, error code: {result}")
    
    def stop_signal(self, signal_type=SignalType.SignalEeg):
        """Stop signal acquisition."""
        result = neurosdk2_lib.bbDeviceStopSignal(self.device_ptr, signal_type.value)
        if result != 0:
            raise RuntimeError(f"Failed to stop signal, error code: {result}")
    
    def is_signal_enabled(self, signal_type=SignalType.SignalEeg):
        """Check if signal acquisition is enabled."""
        enabled = ctypes.c_bool()
        result = neurosdk2_lib.bbDeviceIsSignalEnabled(self.device_ptr, signal_type.value, ctypes.byref(enabled))
        if result != 0:
            raise RuntimeError(f"Failed to check if signal is enabled, error code: {result}")
        return enabled.value
    
    def get_battery_level(self):
        """Get the device battery level."""
        battery = ctypes.c_int()
        result = neurosdk2_lib.bbDeviceReadBatteryPower(self.device_ptr, ctypes.byref(battery))
        if result != 0:
            raise RuntimeError(f"Failed to get battery level, error code: {result}")
        return battery.value

def find_and_connect_brainbit():
    """Find and connect to a BrainBit device."""
    print("Scanning for BrainBit devices...")
    scanner = DeviceScanner()
    scanner.start_scan()
    
    # Scan for 10 seconds
    start_time = time.time()
    found_devices = []
    
    while time.time() - start_time < 10:
        devices_list = scanner.list_devices()
        
        # Filter BrainBit devices
        brainbit_devices = [
            device for device in devices_list 
            if device['type'] in [
                DeviceType.BrainBit.value, 
                DeviceType.BrainBitBlack.value,
                DeviceType.BrainBitBlackBtLE.value,
                DeviceType.BrainBitFlex.value
            ]
        ]
        
        if brainbit_devices:
            found_devices = brainbit_devices
            print(f"Found {len(brainbit_devices)} BrainBit device(s)")
            for i, device in enumerate(brainbit_devices):
                print(f"Device {i+1}: {device['name']} ({device['address']})")
            break
        
        time.sleep(0.5)
    
    # Stop scanning
    scanner.stop_scan()
    
    if not found_devices:
        print("No BrainBit devices found")
        return None
    
    # Connect to the first found device
    device_info = found_devices[0]
    print(f"Connecting to {device_info['name']} ({device_info['address']})...")
    
    try:
        device = BrainBitDevice(device_info['address'], device_info['type'])
        device.connect()
        
        # Wait for connection
        time.sleep(1)
        
        print(f"Connected to {device_info['name']}")
        print(f"Battery level: {device.get_battery_level()}%")
        
        # Start signal acquisition
        device.start_signal()
        print("Signal acquisition started")
        
        return device
    
    except Exception as e:
        print(f"Error connecting to device: {e}")
        return None

def init_plot(fig, axes, lines):
    """Initialize the plot."""
    x_data = np.linspace(-5, 0, buffer_size)
    for i, (ch_name, ch_data) in enumerate(eeg_data.items()):
        lines[i].set_data(x_data, ch_data)
        axes[i].set_xlim(-5, 0)
        axes[i].set_ylim(-100, 100)  # Start with a reasonable range
    return lines

def update_plot(frame, device, fig, axes, lines, status_text):
    """Update the plot with new data."""
    if device is None:
        status_text.set_text("Device disconnected")
        return lines
    
    # Get battery level
    try:
        battery = device.get_battery_level()
        status_text.set_text(f"Connected | Battery: {battery}%")
    except Exception as e:
        status_text.set_text(f"Error: {e}")
    
    # Update the plot data
    with eeg_lock:
        x_data = np.linspace(-5, 0, buffer_size)
        for i, (ch_name, ch_data) in enumerate(eeg_data.items()):
            lines[i].set_data(x_data, ch_data)
            
            # Adjust y-axis limits based on data
            if np.any(ch_data != 0):
                data_range = ch_data[ch_data != 0]
                y_max = max(100, np.max(np.abs(data_range)) * 1.2)
                axes[i].set_ylim(-y_max, y_max)
    
    return lines

def main():
    """Main function."""
    try:
        # Connect to BrainBit
        device = find_and_connect_brainbit()
        if device is None:
            print("Failed to connect to BrainBit")
            return
        
        # Create the figure
        fig, axes = plt.subplots(4, 1, figsize=(12, 8), sharex=True)
        plt.subplots_adjust(hspace=0.4)
        fig.suptitle('BrainBit SDK2 Direct Implementation', fontsize=16)
        
        # Create a line for each channel
        lines = []
        for i, (ch_name, ch_data) in enumerate(eeg_data.items()):
            line, = axes[i].plot([], [], lw=1.5)
            lines.append(line)
            axes[i].set_title(f"Channel {ch_name}")
            axes[i].set_ylabel('μV')
            axes[i].grid(True)
        
        # Set x-axis for the bottom plot
        axes[-1].set_xlabel('Time (s)')
        
        # Status text
        status_text = fig.text(0.5, 0.02, f"Connected | Battery: {device.get_battery_level()}%", 
                            ha='center', fontsize=12, bbox=dict(facecolor='white', alpha=0.7))
        
        # Create animation
        ani = FuncAnimation(
            fig, update_plot, fargs=(device, fig, axes, lines, status_text),
            init_func=lambda: init_plot(fig, axes, lines),
            interval=100, blit=True
        )
        
        # Show the plot
        plt.tight_layout()
        plt.show()
    
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'device' in locals() and device is not None:
            try:
                device.stop_signal()
                device.disconnect()
                print("Device disconnected")
            except Exception as e:
                print(f"Error disconnecting from device: {e}")

if __name__ == "__main__":
    main()
