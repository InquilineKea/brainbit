#!/usr/bin/env python3
"""
BrainBit Minimal Display

A bare-bones EEG visualization with fixed scaling and terminal output.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import time
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

# Create figure and subplots with fixed size
plt.ion()  # Turn on interactive mode
fig, axes = plt.subplots(4, 1, figsize=(8, 10))
plt.tight_layout()

# Set fixed y-limits
for ax in axes:
    ax.set_ylim(-100000, 100000)  # Fixed scale based on signal check
    ax.grid(True)

# Channel names and lines
ch_names = ['T3', 'T4', 'O1', 'O2']
lines = []

# Create a line object for each channel
for i, ax in enumerate(axes):
    line, = ax.plot([], [], lw=1.5)
    lines.append(line)
    ax.set_title(f"Channel {ch_names[i]}")
    ax.set_ylabel('μV')

axes[-1].set_xlabel('Time (s)')

# Initialize x data (5 seconds at 250 Hz)
buffer_size = 250 * 5
x_data = np.linspace(-5, 0, buffer_size)

# Initialize y data buffers
y_data = [np.zeros(buffer_size) for _ in range(4)]

# Connect to BrainBit
print("Connecting to BrainBit...")
params = BrainFlowInputParams()
board = BoardShim(BoardIds.BRAINBIT_BOARD, params)
board.prepare_session()
board.start_stream()
print("Connected and streaming started!")

# Update buffer with new data
def update_buffer(buffer, new_data):
    """Update buffer with new data."""
    if len(new_data) >= len(buffer):
        return new_data[-len(buffer):]
    else:
        buffer = np.roll(buffer, -len(new_data))
        buffer[-len(new_data):] = new_data
        return buffer

# Main loop
try:
    print("\nEEG SIGNALS ARE DISPLAYED IN MATPLOTLIB WINDOW")
    print("Check if the matplotlib window is open on your screen")
    print("Press Ctrl+C to exit\n")
    
    print("CHANNEL STATUS:")
    print("-" * 60)
    
    # Get EEG channels
    eeg_channels = BoardShim.get_eeg_channels(BoardIds.BRAINBIT_BOARD)
    
    # Loop until user interrupts
    while True:
        # Get latest data (1/2 second of data)
        data = board.get_current_board_data(125)
        
        if data.size > 0 and data.shape[1] > 0:
            # Process each channel
            for i, ch in enumerate(eeg_channels):
                if ch < data.shape[0]:
                    # Get channel data
                    channel_data = data[ch]
                    
                    if len(channel_data) > 0:
                        # Update buffer
                        y_data[i] = update_buffer(y_data[i], channel_data)
                        
                        # Update line
                        lines[i].set_data(x_data[:len(y_data[i])], y_data[i])
                        
                        # Print current value
                        current = channel_data[-1] if len(channel_data) > 0 else 0
                        signal_strength = "STRONG" if abs(current) > 10000 else "WEAK"
                        print(f"{ch_names[i]}: Current={current:.2f} μV - {signal_strength}")
            
            print("-" * 60)
            plt.pause(0.1)  # Update display
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nExiting...")
finally:
    # Clean up
    board.stop_stream()
    board.release_session()
    print("Disconnected from BrainBit.")
    plt.close()
