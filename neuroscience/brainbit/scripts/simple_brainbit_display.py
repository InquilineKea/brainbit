#!/usr/bin/env python3
"""
Simple BrainBit Display

A minimal EEG visualization that focuses on displaying raw signal values
"""

import time
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# BrainFlow imports
import brainflow
from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

# Set up the figure and axes
fig, axes = plt.subplots(4, 1, figsize=(10, 8), sharex=True)
plt.subplots_adjust(hspace=0.4)
fig.suptitle('BrainBit EEG Signals', fontsize=16)

# Configure the plots
lines = []
for i, ax in enumerate(axes):
    line, = ax.plot([], [], lw=1.5)
    lines.append(line)
    ax.set_ylim(-500, 500)  # Wide range to ensure signal is visible
    ax.grid(True)

# X-axis for time (5 seconds)
time_data = np.linspace(-5, 0, 1250)

# Initialize data
eeg_data = [np.zeros(1250) for _ in range(4)]
channel_names = ['T3', 'T4', 'O1', 'O2']

# Set up the axes
for i, ax in enumerate(axes):
    ax.set_title(f'{channel_names[i]} Signal')
    ax.set_ylabel('μV')
    
axes[-1].set_xlabel('Time (s)')

def init():
    """Initialize the animation."""
    for i, line in enumerate(lines):
        line.set_data(time_data, eeg_data[i])
    return lines

def get_brainbit_data():
    """Get data from BrainBit device."""
    # Parameters for board
    params = BrainFlowInputParams()
    
    # Start board connection
    board_id = BoardIds.BRAINBIT_BOARD
    BoardShim.enable_dev_board_logger()
    print("Connecting to BrainBit...")
    
    try:
        board = BoardShim(board_id, params)
        board.prepare_session()
        board.start_stream()
        print("Connected to BrainBit!")
        
        # Use the board
        eeg_channels = BoardShim.get_eeg_channels(board_id)
        sampling_rate = BoardShim.get_sampling_rate(board_id)
        print(f"EEG Channels: {eeg_channels}")
        print(f"Sampling Rate: {sampling_rate} Hz")
        
        # Get some initial data (wait for buffer to fill)
        print("Waiting for data...")
        time.sleep(5)
        
        # Get the data
        data = board.get_current_board_data(1250)  # Get 5 seconds of data
        
        # Clean up
        board.stop_stream()
        board.release_session()
        
        # Process data for each channel
        result = []
        for ch in eeg_channels:
            if ch < data.shape[0]:
                channel_data = data[ch]
                if len(channel_data) < 1250:
                    # Pad with zeros if needed
                    padded = np.zeros(1250)
                    padded[-len(channel_data):] = channel_data
                    result.append(padded)
                else:
                    result.append(channel_data[-1250:])
            else:
                result.append(np.zeros(1250))
        
        return result
    
    except Exception as e:
        print(f"Error connecting to BrainBit: {e}")
        return [np.zeros(1250) for _ in range(4)]

def update(frame):
    """Update the animation."""
    global eeg_data
    
    if frame == 0:
        # Get new data from BrainBit
        new_data = get_brainbit_data()
        if new_data:
            eeg_data = new_data
            
            # Update the display with stats
            for i, ax in enumerate(axes):
                if i < len(eeg_data):
                    signal = eeg_data[i]
                    mean = np.mean(signal)
                    std = np.std(signal)
                    max_val = np.max(np.abs(signal))
                    ax.set_title(f'{channel_names[i]}: Mean={mean:.2f}, StdDev={std:.2f}, Max={max_val:.2f} μV')
    
    # Update all lines
    for i, line in enumerate(lines):
        if i < len(eeg_data):
            line.set_data(time_data, eeg_data[i])
            
            # Adjust y limits based on the data
            max_val = np.max(np.abs(eeg_data[i]))
            if max_val > 0:
                axes[i].set_ylim(-max_val*1.2, max_val*1.2)
    
    return lines

# Create animation that runs once
ani = FuncAnimation(fig, update, frames=1, init_func=init, blit=True)

plt.tight_layout()
plt.show()

print("Done!")
