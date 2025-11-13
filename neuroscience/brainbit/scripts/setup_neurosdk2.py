#!/usr/bin/env python3
"""
User-level NeuroSDK2 Setup for macOS

This script sets up the NeuroSDK2 libraries in the user's home directory
without requiring sudo privileges.
"""

import os
import sys
import ctypes
import site
import platform
from pathlib import Path
import shutil

def setup_user_level_library():
    """Set up the NeuroSDK2 library at the user level."""
    print("=== Setting up NeuroSDK2 at user level ===")
    
    # Define source paths (from previous installation)
    home_dir = str(Path.home())
    lib_source = os.path.join(home_dir, "Library", "neurosdk2", "libneurosdk2.dylib")
    
    # Check if the library exists
    if not os.path.exists(lib_source):
        print(f"Error: Library not found at {lib_source}")
        print("Please run the installer script first: python install_neurosdk2.py")
        return False
    
    # Get Python site-packages directory
    site_packages_dir = site.getsitepackages()[0]
    
    # Create a neurosdk2 directory in site-packages if it doesn't exist
    neurosdk_dir = os.path.join(site_packages_dir, "neurosdk2_lib")
    os.makedirs(neurosdk_dir, exist_ok=True)
    
    # Copy the library to the site-packages directory
    lib_dest = os.path.join(neurosdk_dir, "libneurosdk2.dylib")
    print(f"Copying library to: {lib_dest}")
    shutil.copy2(lib_source, lib_dest)
    
    # Create a .pth file to add the library directory to Python's path
    pth_file = os.path.join(site_packages_dir, "neurosdk2_lib.pth")
    with open(pth_file, "w") as f:
        f.write(neurosdk_dir)
    
    print(f"Created path file: {pth_file}")
    
    # Create initialization script
    init_script = os.path.join(site_packages_dir, "neurosdk2_init.py")
    with open(init_script, "w") as f:
        f.write("""
# Initialize NeuroSDK2 library path
import os
import sys
import ctypes
from pathlib import Path

def init_neurosdk2():
    # Try to load from site-packages first
    try:
        import site
        for site_dir in site.getsitepackages():
            lib_path = os.path.join(site_dir, "neurosdk2_lib", "libneurosdk2.dylib")
            if os.path.exists(lib_path):
                return ctypes.CDLL(lib_path)
    except Exception as e:
        print(f"Warning: Could not load from site-packages: {e}")
    
    # Try user library
    try:
        home_dir = str(Path.home())
        lib_path = os.path.join(home_dir, "Library", "neurosdk2", "libneurosdk2.dylib")
        if os.path.exists(lib_path):
            return ctypes.CDLL(lib_path)
    except Exception as e:
        print(f"Warning: Could not load from user library: {e}")
    
    # Try system library
    try:
        return ctypes.CDLL("libneurosdk2.dylib")
    except Exception as e:
        print(f"Warning: Could not load system library: {e}")
    
    raise ImportError("Failed to load NeuroSDK2 library")

# Initialize the library
neurosdk2_lib = init_neurosdk2()
""")
    
    print(f"Created initialization script: {init_script}")
    
    # Create a patch for pyneurosdk2
    patch_script = os.path.join(site_packages_dir, "neurosdk2_patch.py")
    with open(patch_script, "w") as f:
        f.write("""
# Patch pyneurosdk2 to use our library initialization
import os
import sys
import importlib.util
import site

# Find the pyneurosdk2 package
pyneurosdk2_found = False
for site_dir in site.getsitepackages():
    module_path = os.path.join(site_dir, "pyneurosdk2", "__init__.py")
    if os.path.exists(module_path):
        pyneurosdk2_found = True
        
        # Backup the original file if not already done
        backup_path = module_path + ".bak"
        if not os.path.exists(backup_path):
            import shutil
            shutil.copy2(module_path, backup_path)
        
        # Read the original content
        with open(backup_path, "r") as f:
            content = f.read()
        
        # Check if already patched
        if "neurosdk2_init" in content:
            print("pyneurosdk2 already patched")
            break
        
        # Modify to use our library initialization
        modified_content = content.replace(
            "from pyneurosdk2 import managers",
            "import neurosdk2_init\\nfrom pyneurosdk2 import managers"
        )
        
        # Write the modified file
        with open(module_path, "w") as f:
            f.write(modified_content)
        
        print(f"Patched pyneurosdk2 at: {module_path}")
        break

if not pyneurosdk2_found:
    print("pyneurosdk2 package not found")
""")
    
    print(f"Created patch script: {patch_script}")
    
    # Execute the patch
    print("Applying the patch...")
    exec(open(patch_script).read())
    
    print("\n=== User-level setup complete! ===")
    print("The NeuroSDK2 library has been set up at the user level.")
    print("You can now use pyneurosdk2 without sudo privileges.")
    
    return True

def create_brainbit_demo():
    """Create a simple demo script to test the BrainBit with NeuroSDK2."""
    print("\n=== Creating BrainBit SDK2 Demo ===")
    
    demo_script = "brainbit_sdk2_demo.py"
    with open(demo_script, "w") as f:
        f.write('''#!/usr/bin/env python3
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
''')
    
    print(f"Demo script created: {demo_script}")
    print(f"Run it with: python {demo_script}")
    
    return demo_script

def main():
    """Main function."""
    print("=== NeuroSDK2 User-Level Setup ===")
    
    # Check if we're on macOS
    if platform.system() != "Darwin":
        print("This setup script only works on macOS.")
        return
    
    # Set up the user-level library
    if not setup_user_level_library():
        return
    
    # Create the demo script
    demo_script = create_brainbit_demo()
    
    print("\n=== Setup complete! ===")
    print("NeuroSDK2 has been set up successfully at the user level.")
    print(f"Run the demo script to test your BrainBit: python {demo_script}")

if __name__ == "__main__":
    main()
