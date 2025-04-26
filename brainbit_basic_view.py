#!/usr/bin/env python3
"""
BrainBit Basic View

A simple, reliable visualization for BrainBit data that works with raw signal values.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import time

from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds
from brainflow.data_filter import DataFilter, DetrendOperations, FilterTypes

# Global variables
board = None
eeg_channels = None
ch_names = None
sampling_rate = None

# Create the figure and subplots
fig, axes = plt.subplots(4, 1, figsize=(12, 8), sharex=True)
fig.suptitle('BrainBit EEG (Press Q to exit)', fontsize=16)

# Create line objects for each channel
lines = []
for ax in axes:
    line, = ax.plot([], [], lw=1.5)
    lines.append(line)
    ax.grid(True)

# Set up axis labels
for i, ax in enumerate(axes):
    ax.set_ylabel('μV')
    
axes[-1].set_xlabel('Time (s)')

# Initialize data buffers
data_buffers = [[] for _ in range(4)]
timestamp = []

# Buffer size (5 seconds of data)
buffer_size = 250 * 5

def connect_brainbit():
    """Connect to BrainBit device."""
    global board, eeg_channels, ch_names, sampling_rate
    
    # Parameters for BrainBit
    params = BrainFlowInputParams()
    board_id = BoardIds.BRAINBIT_BOARD
    
    print("Connecting to BrainBit...")
    board = BoardShim(board_id, params)
    board.prepare_session()
    
    # Get device info
    eeg_channels = BoardShim.get_eeg_channels(board_id)
    ch_names = BoardShim.get_eeg_names(board_id)
    sampling_rate = BoardShim.get_sampling_rate(board_id)
    
    print(f"Connected to BrainBit!")
    print(f"EEG Channels: {ch_names}")
    print(f"Sampling Rate: {sampling_rate} Hz")
    
    # Set axis titles with channel names
    for i, ax in enumerate(axes):
        if i < len(ch_names):
            ax.set_title(f"Channel {ch_names[i]}")
    
    # Start streaming
    board.start_stream()
    print("Streaming started!")
    
    return True

def init():
    """Initialize the animation."""
    for line in lines:
        line.set_data([], [])
    return lines

def update(frame):
    """Update the animation with new data."""
    global timestamp, data_buffers
    
    if board is None:
        return lines
    
    # Get latest data (1/4 second of data)
    data = board.get_current_board_data(sampling_rate // 4)
    
    if data.size > 0 and data.shape[1] > 0:
        # Get current time
        current_time = time.time()
        
        # Process each channel
        for i, ch in enumerate(eeg_channels):
            if i >= len(lines):
                continue
                
            if ch < data.shape[0]:
                # Extract channel data
                channel_data = data[ch]
                
                if len(channel_data) == 0:
                    continue
                
                # Append new data points to buffer
                data_buffers[i].extend(channel_data)
                
                # Keep buffer size limited
                if len(data_buffers[i]) > buffer_size:
                    data_buffers[i] = data_buffers[i][-buffer_size:]
                
                # Process for display
                display_data = np.array(data_buffers[i])
                
                # Basic detrending (remove DC offset)
                if len(display_data) > 20:  # Need enough points for detrending
                    try:
                        detrended = display_data.copy()
                        DataFilter.detrend(detrended, DetrendOperations.CONSTANT.value)
                        display_data = detrended
                    except Exception as e:
                        print(f"Error in detrending: {e}")
                
                # Update the line
                x_data = np.linspace(-len(display_data)/sampling_rate, 0, len(display_data))
                lines[i].set_data(x_data, display_data)
                
                # Adjust y axis limits based on data
                if len(display_data) > 0:
                    max_abs = max(1, np.max(np.abs(display_data)))
                    axes[i].set_ylim(-max_abs*1.2, max_abs*1.2)
        
        # Set x axis limits
        for ax in axes:
            ax.set_xlim(-buffer_size/sampling_rate, 0)
    
    return lines

def on_key_press(event):
    """Handle key press events."""
    if event.key == 'q':
        plt.close(fig)

def main():
    """Main function."""
    try:
        # Connect to BrainBit
        if not connect_brainbit():
            print("Failed to connect. Exiting.")
            return
        
        # Set up key press handler
        fig.canvas.mpl_connect('key_press_event', on_key_press)
        
        # Create animation
        ani = FuncAnimation(
            fig, update, init_func=init,
            interval=100, blit=True
        )
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.9)
        plt.show()
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Clean up
        if board:
            board.stop_stream()
            board.release_session()
            print("Disconnected from BrainBit.")

if __name__ == "__main__":
    main()
