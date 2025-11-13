#!/usr/bin/env python3
"""
BrainBit SDK2 Demo

A simple demo to test BrainBit functionality using NeuroSDK2.
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Import NeuroSDK2
from pyneurosdk2.device import Device, DeviceInfo, ParameterName
from pyneurosdk2.enums import DeviceState, DeviceType, SamplingFrequency, Signal
from pyneurosdk2.managers import MemoryManager, DeviceScanner

# Global variables
device = None
buffer_size = 1250  # 5 seconds at 250 Hz
eeg_data = {
    "T3": np.zeros(buffer_size),
    "T4": np.zeros(buffer_size),
    "O1": np.zeros(buffer_size),
    "O2": np.zeros(buffer_size)
}

# Create the figure
fig, axes = plt.subplots(4, 1, figsize=(12, 8), sharex=True)
plt.subplots_adjust(hspace=0.4)
fig.suptitle('BrainBit SDK2 Demo', fontsize=16)

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
status_text = fig.text(0.5, 0.02, "Connecting to BrainBit...", ha='center', fontsize=12,
                     bbox=dict(facecolor='white', alpha=0.7))

def init_plot():
    """Initialize the plot."""
    x_data = np.linspace(-5, 0, buffer_size)
    for i, (ch_name, ch_data) in enumerate(eeg_data.items()):
        lines[i].set_data(x_data, ch_data)
        axes[i].set_xlim(-5, 0)
        axes[i].set_ylim(-100, 100)  # Start with a reasonable range
    return lines

def update_plot(frame):
    """Update the plot with new data."""
    if device is None or not device.is_connected():
        status_text.set_text("Device disconnected")
        return lines
    
    # Update the plot data
    x_data = np.linspace(-5, 0, buffer_size)
    for i, (ch_name, ch_data) in enumerate(eeg_data.items()):
        lines[i].set_data(x_data, ch_data)
        
        # Adjust y-axis limits based on data
        if np.any(ch_data != 0):
            data_range = ch_data[ch_data != 0]
            y_max = max(100, np.max(np.abs(data_range)) * 1.2)
            axes[i].set_ylim(-y_max, y_max)
    
    status_text.set_text(f"Connected to {device.name} | Battery: {device.read_parameter(ParameterName.BattPower)}%")
    return lines

def on_signal_received(sender, signal_type, signal_data):
    """Callback for signal data reception."""
    if signal_type == Signal.SignalEeg:
        ch_t3 = 0
        ch_t4 = 1
        ch_o1 = 2
        ch_o2 = 3
        
        # Check if we have the expected number of channels
        if len(signal_data) >= 4:
            # Update the data buffers (roll and append new data)
            eeg_data["T3"] = np.roll(eeg_data["T3"], -1)
            eeg_data["T3"][-1] = signal_data[ch_t3]
            
            eeg_data["T4"] = np.roll(eeg_data["T4"], -1)
            eeg_data["T4"][-1] = signal_data[ch_t4]
            
            eeg_data["O1"] = np.roll(eeg_data["O1"], -1)
            eeg_data["O1"][-1] = signal_data[ch_o1]
            
            eeg_data["O2"] = np.roll(eeg_data["O2"], -1)
            eeg_data["O2"][-1] = signal_data[ch_o2]

def find_and_connect_brainbit():
    """Find and connect to a BrainBit device."""
    global device
    
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
            info for info in devices_list 
            if info.device_type in [
                DeviceType.BrainBit.value, 
                DeviceType.BrainBitBlack.value,
                DeviceType.BrainBitBlackBtLE.value,
                DeviceType.BrainBitFlex.value
            ]
        ]
        
        if brainbit_devices:
            found_devices = brainbit_devices
            break
        
        time.sleep(0.5)
    
    # Stop scanning
    scanner.stop_scan()
    
    if not found_devices:
        print("No BrainBit devices found")
        return False
    
    # Connect to the first found device
    info = found_devices[0]
    print(f"Connecting to {info.name} ({info.address})...")
    
    try:
        device = Device(info)
        device.connect()
        
        # Wait for connection
        timeout = time.time() + 5
        while not device.is_connected() and time.time() < timeout:
            time.sleep(0.1)
        
        if not device.is_connected():
            print("Failed to connect to device")
            return False
        
        print(f"Connected to {device.name}")
        
        # Register signal callback
        device.signal_received.append(on_signal_received)
        
        # Start signal acquisition
        device.enable_signal()
        print("Signal acquisition started")
        
        return True
    
    except Exception as e:
        print(f"Error connecting to device: {e}")
        return False

def close_device():
    """Close the device connection."""
    global device
    if device and device.is_connected():
        device.disable_signal()
        device.disconnect()
        print("Device disconnected")

def main():
    """Main function."""
    try:
        # Connect to BrainBit
        if not find_and_connect_brainbit():
            print("Failed to connect to BrainBit")
            return
        
        # Create animation
        ani = FuncAnimation(
            fig, update_plot, init_func=init_plot,
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
        close_device()

if __name__ == "__main__":
    main()
